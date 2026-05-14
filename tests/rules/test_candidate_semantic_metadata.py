from __future__ import annotations

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine import game_decision_runtime
from warhammer40k_ai.engine.candidate_semantics import (
    SEMANTIC_NUMERIC_KEYS,
    ensure_candidate_semantic_metadata,
)
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ALLOCATE_MELEE_TARGETS,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_DICE_REROLL,
    DECISION_SELECT_UNIT,
    DECISION_USE_GILDED_CHAMPION,
)
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.roster.player import Player


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_request_decision_adds_semantic_metadata_keys_to_candidates() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )

    game.request_decision(request)

    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        for key in SEMANTIC_NUMERIC_KEYS:
            assert key in metadata
        assert isinstance(metadata.get("rules_provenance_refs"), list)
        assert request.context["rules_bundle_id"] in metadata["rules_provenance_refs"]


def test_request_decision_sets_context_before_semantic_projection(monkeypatch) -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )

    captured: dict[str, object] = {}
    original = game_decision_runtime.ensure_candidate_semantic_metadata

    def _spy(request_obj, *, rules_bundle_id, rules_bundle=None):
        captured["context"] = dict(getattr(request_obj, "context", {}) or {})
        return original(request_obj, rules_bundle_id=rules_bundle_id, rules_bundle=rules_bundle)

    monkeypatch.setattr(game_decision_runtime, "ensure_candidate_semantic_metadata", _spy)
    game.request_decision(request)

    observed = dict(captured.get("context", {}) or {})
    assert isinstance(observed.get("descriptor_ids"), dict)
    assert str(observed.get("descriptor_bundle_id", "") or "")
    assert str(observed.get("rules_bundle_id", "") or "")
    assert "time_budget_ms" in observed


def test_command_reroll_request_gets_tool_semantic_projection_metadata() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Select dice to reroll",
        player_id=player.id,
        context={
            "roll_id": 1,
            "roll_spec": {
                "dice_count": 1,
                "faces": 6,
                "reason": "Hit roll (1D6)",
                "command_reroll_allowed": True,
                "command_reroll_mode": "one",
            },
        },
        options=[
            DecisionOption.create("Keep", payload={"action_id": "none", "label": "Keep"}),
            DecisionOption.create(
                "Command Re-roll",
                payload={
                    "action_id": "command_reroll",
                    "label": "Command Re-roll",
                    "ability_key": "command_reroll",
                    "ability_name": "COMMAND RE-ROLL",
                    "stratagem_name": "COMMAND RE-ROLL",
                    "tool_id": "stratagem:command_reroll",
                    "tool_type": "stratagem",
                    "source": "command",
                    "mode": "one",
                    "eligible_die_ids": ["1:0"],
                    "max_select": 1,
                    "cp_cost": 1,
                    "consume_cp": True,
                    "is_command": True,
                    "semantic_tags": ["reroll", "command", "resource"],
                },
            ),
        ],
    )

    game.request_decision(request)

    command_reroll_candidate = next(
        candidate
        for candidate in list(request.candidates or [])
        if str(candidate.params.get("ability_key", "") or "") == "command_reroll"
    )
    metadata = dict(command_reroll_candidate.metadata or {})
    context = dict(request.context or {})

    assert metadata["semantic_projection_kind"] == "tool"
    assert str(context.get("rules_bundle_id", "") or "")
    assert isinstance(context.get("descriptor_ids"), dict)
    assert metadata["rules_provenance_refs"] == [context["rules_bundle_id"]]
    assert any(abs(float(metadata.get(key, 0.0) or 0.0)) > 0.0 for key in SEMANTIC_NUMERIC_KEYS)


def test_semantic_augmenter_preserves_existing_numeric_values() -> None:
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id="player_1",
        options=[DecisionOption.create("Declare", payload={"action": "declare"})],
        candidates=[
            CandidateAction(
                action_id="candidate_1",
                params={"action": "declare"},
                metadata={"projected_trade_ev": 1.75},
            )
        ],
        mask=[True],
    )
    ensure_candidate_semantic_metadata(request, rules_bundle_id="rules_bundle:test")

    metadata = dict(request.candidates[0].metadata or {})
    assert metadata["projected_trade_ev"] == 1.75
    for key in SEMANTIC_NUMERIC_KEYS:
        assert key in metadata
    assert metadata["rules_provenance_refs"] == ["rules_bundle:test"]


def _rules_bundle_with_suffix(suffix: str) -> dict[str, str]:
    return {
        "core_rules_id": f"core_{suffix}",
        "rules_commentary_id": f"commentary_{suffix}",
        "mission_pack_id": f"mission_{suffix}",
        "terrain_pack_id": f"terrain_{suffix}",
        "dataslate_id": f"dataslate_{suffix}",
        "points_id": f"points_{suffix}",
        "faction_pack_id": f"faction_{suffix}",
        "detachment_pack_id": f"detachment_{suffix}",
    }


def _single_candidate_request(
    decision_type: str,
    *,
    params: dict,
    context: dict | None = None,
) -> DecisionRequest:
    return DecisionRequest.create(
        decision_type,
        "Semantic projection test",
        player_id="player_1",
        options=[DecisionOption.create("Apply", payload=dict(params or {}))],
        context=dict(context or {}),
        candidates=[
            CandidateAction(
                action_id=f"{decision_type}:candidate",
                params=dict(params or {}),
                metadata={},
            )
        ],
        mask=[True],
    )


def _roll_die(roll_id: int, index: int, value: int, *, faces: int = 6) -> dict[str, object]:
    return {
        "die_id": f"{int(roll_id)}:{int(index)}",
        "value": int(value),
        "faces": int(faces),
        "raw_value": int(value),
        "raw_faces": int(faces),
        "is_derived": False,
        "derived_kind": None,
        "reroll_count": 0,
        "rerolled_from": None,
    }


def _build_roll_state(
    *,
    roll_id: int,
    player_id: str,
    spec: dict,
    dice_values: list[int],
    per_die_success: dict[str, bool | None],
    sum_success: bool | None,
) -> DiceRollState:
    dice = [_roll_die(roll_id, index, value) for index, value in enumerate(list(dice_values or []))]
    return DiceRollState(
        roll_id=int(roll_id),
        player_id=str(player_id),
        spec=dict(spec or {}),
        status="rolled",
        dice=dice,
        total=int(sum(int(value) for value in list(dice_values or []))),
        sorted_ids=[str(die["die_id"]) for die in list(dice or [])],
        per_die_success=dict(per_die_success or {}),
        sum_success=sum_success,
        reroll_options=[],
        reroll_history=[],
        final=False,
    )


def _reroll_request_from_roll_state(
    *,
    game: Game,
    player: Player,
    roll_state: DiceRollState,
    command_mode: str,
    eligible_die_ids: list[str],
) -> DecisionRequest:
    game.roll_manager.rolls[int(roll_state.roll_id)] = roll_state
    request = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Select dice to reroll",
        player_id=player.id,
        context={"roll_id": int(roll_state.roll_id)},
        options=[
            DecisionOption.create(
                "Keep",
                payload={
                    "action_id": "none",
                    "label": "Keep",
                    "source": "none",
                    "mode": "none",
                },
            ),
            DecisionOption.create(
                "Command Re-roll",
                payload={
                    "action_id": "command_reroll",
                    "label": "Command Re-roll",
                    "ability_key": "command_reroll",
                    "ability_name": "COMMAND RE-ROLL",
                    "stratagem_name": "COMMAND RE-ROLL",
                    "tool_id": "stratagem:command_reroll",
                    "tool_type": "stratagem",
                    "source": "command",
                    "mode": str(command_mode),
                    "eligible_die_ids": list(eligible_die_ids or []),
                    "max_select": None if str(command_mode) in {"whole", "all"} else 1,
                    "cp_cost": 1,
                    "consume_cp": True,
                    "is_command": True,
                    "semantic_tags": ["reroll", "command", "resource"],
                },
            ),
        ],
    )
    game.request_decision(request)
    return request


def _candidate_by_action_id(request: DecisionRequest, action_id: str) -> CandidateAction:
    return next(candidate for candidate in list(request.candidates or []) if str(candidate.action_id or "") == str(action_id))


@pytest.mark.parametrize(
    ("decision_type", "params", "context", "expected_kind"),
    [
        (
            DECISION_MOVE_UNIT,
            {"action": "confirm", "unit_id": "unit_1", "movement_type": "move"},
            {
                "movement_intent": {
                    "target_region_ids": ["region_1"],
                    "target_opportunity_ids": ["opp_1"],
                    "desired_affordances": ["HOLD_SCORE_SOURCE"],
                    "screen_deny_targets": ["lane_1"],
                    "weights": {
                        "score": 0.55,
                        "deny": 0.2,
                        "safety": 0.25,
                        "coherency": 0.2,
                        "action_enable": 0.2,
                        "trade": 0.1,
                    },
                },
                "score_window_state": {"windows": [{"id": "window_1"}]},
            },
            "movement",
        ),
        (
            DECISION_DECLARE_SHOTS,
            {
                "action": "declare",
                "unit_id": "unit_1",
                "target_unit_ids": ["target_a", "target_b"],
                "declared_shots": [{"weapon_id": "weapon_1", "shots": 4}],
            },
            {
                "opportunity_catalog": {
                    "priority": [{"id": "priority_1"}],
                    "denial": [{"id": "deny_1"}],
                }
            },
            "targeting",
        ),
        (
            DECISION_DECLARE_CHARGE,
            {
                "action": "declare",
                "unit_id": "unit_1",
                "target_unit_ids": ["target_a"],
                "charge_distance": 7,
            },
            {},
            "charge",
        ),
        (
            DECISION_SELECT_UNIT,
            {"unit_id": "unit_1"},
            {
                "phase_name": "SHOOTING_PHASE",
                "phase_step": "SHOOT_UNITS",
                "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
            },
            "targeting",
        ),
        (
            DECISION_ALLOCATE_MELEE_TARGETS,
            {
                "action": "allocate",
                "attack_declarations": [
                    {
                        "model_id": "model_1",
                        "wargear_id": "wargear_1",
                        "profile_name": "talons",
                        "target_unit_id": "target_a",
                        "attacks_override": 4,
                    }
                ],
            },
            {},
            "fight",
        ),
        (
            DECISION_USE_GILDED_CHAMPION,
            {
                "action": "use",
                "model_id": "model_1",
                "ability_key": "precision_cut",
                "ability_name": "Precision Strike",
                "cp_cost": 1,
            },
            {"tool_descriptor_ids": ["tool_descriptor:stratagem:001"]},
            "tool",
        ),
    ],
)
def test_semantic_projection_value_shifts_with_bundle_change(
    decision_type: str,
    params: dict,
    context: dict,
    expected_kind: str,
) -> None:
    old_bundle = _rules_bundle_with_suffix("old")
    new_bundle = _rules_bundle_with_suffix("new")
    old_bundle_id = "rules_bundle:old"
    new_bundle_id = "rules_bundle:new"

    old_request = _single_candidate_request(decision_type, params=params, context=context)
    new_request = _single_candidate_request(decision_type, params=params, context=context)
    ensure_candidate_semantic_metadata(
        old_request,
        rules_bundle_id=old_bundle_id,
        rules_bundle=old_bundle,
    )
    ensure_candidate_semantic_metadata(
        new_request,
        rules_bundle_id=new_bundle_id,
        rules_bundle=new_bundle,
    )

    old_metadata = dict(old_request.candidates[0].metadata or {})
    new_metadata = dict(new_request.candidates[0].metadata or {})
    assert old_metadata["semantic_projection_kind"] == expected_kind
    assert new_metadata["semantic_projection_kind"] == expected_kind
    assert old_bundle_id in old_metadata["rules_provenance_refs"]
    assert new_bundle_id in new_metadata["rules_provenance_refs"]

    value_pairs = [
        (
            float(old_metadata.get(key, 0.0)),
            float(new_metadata.get(key, 0.0)),
        )
        for key in SEMANTIC_NUMERIC_KEYS
    ]
    assert any(old_value != new_value for old_value, new_value in value_pairs)


def test_reroll_request_backfills_roll_state_before_semantic_projection() -> None:
    game, player = _build_game()
    roll_state = _build_roll_state(
        roll_id=17,
        player_id=player.id,
        spec={
            "dice_count": 2,
            "faces": 6,
            "reason": "Hit roll pool",
            "roll_type": "hit",
            "target": 3,
            "target_op": "gte",
        },
        dice_values=[1, 5],
        per_die_success={"17:0": False, "17:1": True},
        sum_success=None,
    )
    request = _reroll_request_from_roll_state(
        game=game,
        player=player,
        roll_state=roll_state,
        command_mode="one",
        eligible_die_ids=["17:0", "17:1"],
    )

    context = dict(request.context or {})
    command_candidate = _candidate_by_action_id(request, "command_reroll")
    command_metadata = dict(command_candidate.metadata or {})

    assert context["roll_state"]["total"] == 6
    assert context["roll_spec"]["roll_type"] == "hit"
    assert context["roll_state"]["per_die_success"]["17:0"] is False
    assert command_metadata["semantic_projection_kind"] == "tool"
    assert float(command_metadata["projected_trade_ev"]) > 0.0


def test_command_reroll_semantics_prefer_bad_single_die_reroll_over_none() -> None:
    game, player = _build_game()
    roll_state = _build_roll_state(
        roll_id=21,
        player_id=player.id,
        spec={
            "dice_count": 2,
            "faces": 6,
            "reason": "Hit roll pool",
            "roll_type": "hit",
            "target": 3,
            "target_op": "gte",
        },
        dice_values=[1, 5],
        per_die_success={"21:0": False, "21:1": True},
        sum_success=None,
    )
    request = _reroll_request_from_roll_state(
        game=game,
        player=player,
        roll_state=roll_state,
        command_mode="one",
        eligible_die_ids=["21:0", "21:1"],
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    keep_candidate = _candidate_by_action_id(request, "none")
    command_candidate = _candidate_by_action_id(request, "command_reroll")

    assert controller._semantic_score(request, command_candidate) > controller._semantic_score(request, keep_candidate)


def test_command_reroll_semantics_avoid_already_successful_whole_rolls() -> None:
    game, player = _build_game()
    roll_state = _build_roll_state(
        roll_id=31,
        player_id=player.id,
        spec={
            "dice_count": 2,
            "faces": 6,
            "reason": "Charge roll",
            "roll_type": "charge",
            "sum_target": 7,
            "sum_op": "gte",
        },
        dice_values=[6, 5],
        per_die_success={"31:0": None, "31:1": None},
        sum_success=True,
    )
    request = _reroll_request_from_roll_state(
        game=game,
        player=player,
        roll_state=roll_state,
        command_mode="whole",
        eligible_die_ids=["31:0", "31:1"],
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    keep_candidate = _candidate_by_action_id(request, "none")
    command_candidate = _candidate_by_action_id(request, "command_reroll")

    assert controller._semantic_score(request, keep_candidate) > controller._semantic_score(request, command_candidate)


def test_command_reroll_semantics_handle_low_is_better_whole_rolls() -> None:
    game, player = _build_game()
    roll_state = _build_roll_state(
        roll_id=41,
        player_id=player.id,
        spec={
            "dice_count": 2,
            "faces": 6,
            "reason": "Battle-shock test",
            "roll_type": "battle_shock",
            "sum_target": 6,
            "sum_op": "lte",
        },
        dice_values=[5, 4],
        per_die_success={"41:0": None, "41:1": None},
        sum_success=False,
    )
    request = _reroll_request_from_roll_state(
        game=game,
        player=player,
        roll_state=roll_state,
        command_mode="whole",
        eligible_die_ids=["41:0", "41:1"],
    )
    controller = HeadlessPolicyDecisionController(game=None, auto_attach=False)

    keep_candidate = _candidate_by_action_id(request, "none")
    command_candidate = _candidate_by_action_id(request, "command_reroll")

    assert controller._semantic_score(request, command_candidate) > controller._semantic_score(request, keep_candidate)
