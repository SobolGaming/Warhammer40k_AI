from __future__ import annotations

import sys

import warhammer40k_ai.engine.decision_record as decision_record_module
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_record_determinism import (
    decision_record_determinism_digest,
    decision_record_determinism_signature,
)
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.decision_requests import build_player_color_selection_requests
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.units.wargear import Wargear


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    return game, player


def test_decision_record_valid_choice_has_chosen_action_in_candidates() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True

    record = game.decision_record_store.records[-1]
    action_ids = {str(c["action_id"]) for c in record["candidates"]}
    assert record["valid"] is True
    assert record["chosen_action_id"] in action_ids
    assert str(record.get("descriptor_bundle_id", "")).startswith("descriptor_bundle:")
    boundary = dict(record.get("version_adapter_boundary", {}) or {})
    assert boundary["rules_bundle_id"] == record["rules_bundle_id"]
    assert boundary["descriptor_bundle_id"] == record["descriptor_bundle_id"]
    assert boundary["descriptor_ids"] == record["descriptor_ids"]


def test_decision_record_invalid_attempt_logs_rejection() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id="not-an-option",
        payload={"foo": "bar"},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is False

    record = game.decision_record_store.records[-1]
    assert record["valid"] is False
    assert record["invalid_attempt"]["params"] == {"foo": "bar"}
    assert str(record["rejection_reason"])


def test_decision_record_store_merges_duplicate_decision_id_records() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )

    first = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    second = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=("richer-context",),
        value={"applied": True},
        wall_clock_ms=9,
    )

    assert first["decision_id"] == second["decision_id"]
    assert len(game.decision_record_store.records) == 1
    record = game.decision_record_store.records[0]
    assert record["wall_clock_ms"] == 9
    immediate = record["outcome"]["immediate_deltas"]
    assert immediate["errors"] == ["richer-context"]
    assert immediate["value"] == {"applied": True}


def test_decision_record_outcome_serializes_wargear_profiles_without_object_reprs() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[DecisionOption.create("Yes", payload={"choice": True})],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    wargear = Wargear(
        {
            "name": "Executioner - strike",
            "type": "Melee",
            "range": "Melee",
            "A": "4",
            "BS_WS": "2+",
            "S": "5",
            "AP": "-3",
            "D": "2",
            "description": "Precision",
        }
    )
    profile = wargear.profiles["strike"]

    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value={"weapon_profile": profile},
        wall_clock_ms=1,
    )

    serialized_profile = record["outcome"]["immediate_deltas"]["value"]["weapon_profile"]
    assert " object at 0x" not in str(record["outcome"])
    assert serialized_profile == {
        "__wargear_profile__": {
            "profile_name": "strike",
            "parent_wargear_name": "Executioner",
            "parent_wargear_type": "Melee",
            "wargear_data": {
                "range": "Melee",
                "A": "4",
                "BS_WS": "2+",
                "S": "5",
                "AP": "-3",
                "D": "2",
                "description": "Precision",
            },
        }
    }


def test_decision_seed_does_not_depend_on_request_created_at() -> None:
    game_one, player_one = _build_game()
    game_two, player_two = _build_game()
    game_two.random_source.setstate(game_one.random_source.getstate())
    request_one = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player_one.id,
        options=[DecisionOption.create("Yes", payload={"choice": True})],
    )
    request_two = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player_two.id,
        options=[DecisionOption.create("Yes", payload={"choice": True})],
    )
    request_two.decision_id = request_one.decision_id
    request_one.created_at = 1.0
    request_two.created_at = 999.0
    result_one = DecisionResult(
        decision_id=request_one.decision_id,
        player_id=player_one.id,
        option_id=request_one.options[0].option_id,
        payload={},
    )
    result_two = DecisionResult(
        decision_id=request_two.decision_id,
        player_id=player_two.id,
        option_id=request_two.options[0].option_id,
        payload={},
    )

    record_one = game_one.decision_record_store.record_resolution(
        request_one,
        result_one,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    record_two = game_two.decision_record_store.record_resolution(
        request_two,
        result_two,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=2,
    )

    assert record_one["decision_seed"] == record_two["decision_seed"]


def test_decision_record_determinism_signature_excludes_wall_clock_telemetry() -> None:
    base = {
        "turn_id": 1,
        "phase": "MOVEMENT_PHASE",
        "decision_id": "decision:1",
        "decision_type": DECISION_MOVE_UNIT,
        "global_seed": 7,
        "decision_seed": 9,
        "chosen_action_id": "MOVE_UNIT:1",
        "valid": True,
        "human_action_injected": False,
        "wall_clock_ms": 4,
        "request_context": {
            "unit_id": "unit-1",
            "expires_at": 123.0,
            "roll_state": {"resolved_at": 10.0, "result": [4, 5]},
        },
        "candidates": [
            {
                "action_id": "MOVE_UNIT:1",
                "params": {"unit_id": "unit-1", "expires_at": 123.0},
                "metadata": {"candidate_kind": "move", "solver_ms": 3, "fallback_mode": False},
            }
        ],
        "mask": [True],
        "outcome": {"immediate_deltas": {"apply_ok": True, "value": "<Thing object at 0x123abc>"}},
    }
    profiled = {
        **base,
        "wall_clock_ms": 40,
        "request_context": {
            "unit_id": "unit-1",
            "expires_at": 999.0,
            "roll_state": {"resolved_at": 99.0, "result": [4, 5]},
        },
        "candidates": [
            {
                "action_id": "MOVE_UNIT:1",
                "params": {"unit_id": "unit-1", "expires_at": 999.0},
                "metadata": {"candidate_kind": "move", "solver_ms": 30, "fallback_mode": False},
            }
        ],
        "outcome": {"immediate_deltas": {"apply_ok": True, "value": "<Thing object at 0x999def>"}},
    }

    assert decision_record_determinism_signature(base) == decision_record_determinism_signature(profiled)
    assert decision_record_determinism_digest([base]) == decision_record_determinism_digest([profiled])


def test_decision_record_state_snapshot_has_recursion_headroom(monkeypatch) -> None:
    monkeypatch.setenv("WH40K_VALIDATE_DECISION_RECORDS", "0")
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm action?",
        player_id=player.id,
        options=[DecisionOption.create("Yes", payload={"choice": True})],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )

    def _deep_payload(depth: int) -> dict[str, object]:
        if depth <= 0:
            return {"ok": True}
        return {"next": _deep_payload(depth - 1)}

    monkeypatch.setattr(decision_record_module, "_default_omniscient_state", lambda _game: _deep_payload(220))
    monkeypatch.setattr(decision_record_module, "_default_player_obs_state", lambda _game: {"p1": _deep_payload(220)})

    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(180)
    try:
        record = game.decision_record_store.record_resolution(
            request,
            result,
            ok=True,
            errors=(),
            value=None,
            wall_clock_ms=1,
        )
    finally:
        sys.setrecursionlimit(previous_limit)

    assert record["omniscient_state"]["next"]
    assert sys.getrecursionlimit() == previous_limit


def test_decision_record_store_persists_resolved_option_payload_in_candidate_metadata() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        "Declare shots",
        player_id=player.id,
        options=[
            DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": "unit-1"}),
        ],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={
            "declarations": [
                {
                    "attacker_unit_id": "unit-1",
                    "target_unit_id": "target-1",
                    "weapon_key": "bolt rifle",
                    "attacks": 3,
                }
            ]
        },
    )

    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )

    chosen = next(
        candidate
        for candidate in list(record["candidates"] or [])
        if candidate["action_id"] == record["chosen_action_id"]
    )
    assert chosen["metadata"]["resolved_result_payload"] == result.payload


def test_decision_record_human_action_candidate_injection_for_move_payload() -> None:
    game, player = _build_game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": "unit-1", "movement_type": "move", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": "unit-1", "movement_type": "move", "action": "skip"},
            ),
        ],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={
            "model_positions": [
                {
                    "model_id": "model-1",
                    "position": [10.0, 8.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
    )
    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    action_ids = {str(c["action_id"]) for c in record["candidates"]}
    injected = [c for c in record["candidates"] if c.get("metadata", {}).get("source") == "HumanActionCandidate"]
    assert record["human_action_injected"] is True
    assert record["chosen_action_id"] in action_ids
    assert len(injected) == 1


def test_decision_record_does_not_inject_duplicate_when_candidate_contains_move_payload() -> None:
    game, player = _build_game()
    payload = {
        "unit_id": "unit-1",
        "movement_type": "move",
        "action": "confirm",
        "model_positions": [
            {
                "model_id": "model-1",
                "position": [10.0, 8.0, 0.0],
                "facing": 0.0,
            }
        ],
    }
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload=payload,
            ),
        ],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload=dict(payload),
    )
    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )

    injected = [c for c in record["candidates"] if c.get("metadata", {}).get("source") == "HumanActionCandidate"]
    assert record["human_action_injected"] is False
    assert record["chosen_action_id"] == request.options[0].payload["action_id"]
    assert injected == []


def test_decision_record_matches_move_payload_when_result_includes_action_id() -> None:
    game, player = _build_game()
    payload = {
        "unit_id": "unit-1",
        "movement_type": "deploy",
        "action": "confirm",
        "placement_candidate_id": "candidate:1",
        "placement_candidate_index": 1,
        "deployment_anchor": [10.0, 8.0],
        "model_positions": [
            {
                "model_id": "model-1",
                "position": [10.0, 8.0, 0.0],
                "facing": 0.0,
            }
        ],
        "action_id": "MOVE_UNIT:test:deployment:candidate:1",
    }
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy unit",
        player_id=player.id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload=dict(payload),
            ),
        ],
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload=dict(payload),
    )

    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )

    injected = [c for c in record["candidates"] if c.get("metadata", {}).get("source") == "HumanActionCandidate"]
    assert record["human_action_injected"] is False
    assert record["chosen_action_id"] == payload["action_id"]
    assert injected == []


def test_decision_record_player_color_candidates_are_deterministic_and_valid() -> None:
    player_one = Player("P1")
    player_two = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player_one, player_two])

    requests = build_player_color_selection_requests(game, [player_two], queue_requests=True)
    assert len(requests) == 1
    request = requests[0]
    chosen_option = request.options[4]
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player_two.id,
        option_id=chosen_option.option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is True

    record = game.decision_record_store.records[-1]
    assert record["valid"] is True
    assert record["decision_type"] == DECISION_CHOOSE_PLAYER_COLOR
    candidate_action_ids = [str(candidate["action_id"]) for candidate in list(record["candidates"] or [])]
    assert candidate_action_ids == sorted(candidate_action_ids)
    assert all(
        action_id.startswith(f"{DECISION_CHOOSE_PLAYER_COLOR}:{player_two.id}:")
        for action_id in candidate_action_ids
    )
    assert str(record["chosen_action_id"]) == str(chosen_option.payload["action_id"])

    chosen_candidate = next(
        candidate
        for candidate in list(record["candidates"] or [])
        if str(candidate.get("action_id", "")) == str(record["chosen_action_id"])
    )
    rgb = list(dict(chosen_candidate.get("params", {}) or {}).get("rgb", []) or [])
    assert len(rgb) == 3
    assert all(0 <= int(channel) <= 255 for channel in rgb)
    assert int(dict(chosen_candidate.get("params", {}) or {}).get("hue_degrees", 0)) % 15 == 0


def test_decision_record_store_prunes_old_records_when_limit_reached() -> None:
    game, player = _build_game()
    game.decision_record_store.max_records = 2

    decision_ids: list[str] = []
    for _ in range(3):
        request = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Confirm action?",
            player_id=player.id,
            options=[
                DecisionOption.create("Yes", payload={"choice": True}),
                DecisionOption.create("No", payload={"choice": False}),
            ],
        )
        decision_ids.append(str(request.decision_id))
        game.request_decision(request)
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=request.options[0].option_id,
            payload={},
        )
        apply_result = game.resolve_decision(result)
        assert apply_result.ok is True

    assert len(game.decision_record_store.records) == 2
    assert game.decision_record_store.dropped_records == 1
    remaining_ids = [str(r.get("decision_id", "")) for r in game.decision_record_store.records]
    assert remaining_ids == decision_ids[-2:]


def test_decision_record_default_retention_limit_is_4096(monkeypatch) -> None:
    monkeypatch.delenv("WH40K_DECISION_RECORD_MAX", raising=False)

    game, _player = _build_game()

    assert decision_record_module._decision_record_limit() == 4096
    assert game.decision_record_store.max_records == 4096


def test_decision_record_game_id_is_stable_within_a_single_game() -> None:
    game, player = _build_game()

    for _ in range(2):
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
        result = DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=request.options[0].option_id,
            payload={},
        )
        apply_result = game.resolve_decision(result)
        assert apply_result.ok is True

    records = list(game.decision_record_store.records or [])
    assert len(records) == 2
    game_ids = {str(record.get("game_id", "") or "") for record in records}
    assert len(game_ids) == 1
    assert all(str(game_id).startswith("game:") for game_id in game_ids)


def test_decision_record_validator_rejects_missing_army_build_state_surface() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    broken = dict(record)
    broken["omniscient_state"] = dict(record["omniscient_state"])
    broken["omniscient_state"].pop("army_build_state", None)

    errors = game.decision_record_store._validator.validate(broken)
    assert any("omniscient_state missing required fields: army_build_state" in err for err in errors)


def test_decision_record_validator_rejects_player_obs_state_viewer_mismatch() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    broken = dict(record)
    broken["player_obs_state"] = {
        key: dict(value)
        for key, value in dict(record["player_obs_state"] or {}).items()
    }
    only_key = next(iter(broken["player_obs_state"]))
    broken["player_obs_state"][only_key]["viewer_player_id"] = "different-player-id"

    errors = game.decision_record_store._validator.validate(broken)
    assert any("viewer_player_id must match player_obs_state key" in err for err in errors)


def test_decision_record_validator_rejects_unbound_objective_surface_ids() -> None:
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
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )
    record = game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value=None,
        wall_clock_ms=1,
    )
    broken = dict(record)
    broken["omniscient_state"] = dict(record["omniscient_state"])
    broken["omniscient_state"]["objectives"] = [
        {
            "objective_id": "objective:test",
            "objective_site_id": "objective_site:test",
            "site_kind": "MARKER",
            "geometry": {
                "kind": "MARKER",
                "position": [0.0, 0.0, 0.0],
                "control_radius": 3.0,
                "feature_key": "",
                "feature_label": "",
            },
            "control_region": {
                "region_id": "region:objective:test",
                "kind": "OBJECTIVE_CONTROL_RADIUS",
                "objective_id": "objective:test",
                "objective_site_id": "objective_site:test",
                "center": [0.0, 0.0, 0.0],
                "radius": 3.0,
                "metadata": {},
            },
            "score_sources": [
                {
                    "score_source_id": "score_source:objective:test",
                    "kind": "OBJECTIVE_CONTROL",
                    "objective_id": "objective:test",
                    "objective_site_id": "objective_site:test",
                    "label": "Objective",
                    "controller_player_id": "",
                    "points_value": 5,
                    "metadata": {},
                }
            ],
        }
    ]
    broken["omniscient_state"]["control_regions"] = [
        {
            "region_id": "region:unknown",
            "kind": "OBJECTIVE_CONTROL_RADIUS",
        }
    ]
    broken["omniscient_state"]["scoring_surfaces"] = [
        {
            "score_source_id": "score_source:unknown",
            "kind": "OBJECTIVE_CONTROL",
        }
    ]

    errors = game.decision_record_store._validator.validate(broken)
    assert any("region_id is not declared by any objective.control_region" in err for err in errors)
    assert any("score_source_id is not declared by any objective.score_sources" in err for err in errors)
