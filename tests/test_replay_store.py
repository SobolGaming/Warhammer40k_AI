from __future__ import annotations

import json
import logging
from types import MethodType, SimpleNamespace
import uuid

from warhammer40k_ai.engine import command_dispatcher
from warhammer40k_ai.engine import decision_dispatcher
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.command_dispatcher import register_command_handler
from warhammer40k_ai.engine.command_kinds import CMD_RESOLVE_DECISION
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_dispatcher import register_decision_handler
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay_store import (
    REPLAY_RECORDING_GROUP,
    ReplayStoreReader,
    _pack_json,
    _unpack_json,
    enable_decision_replay_recording,
)
from warhammer40k_ai.roster.player import Player
from warhammer40k_ai.utility import dice as dice_mod
from warhammer40k_ai.utility.game_context import game_context

TEST_REPLAY_NOP_COMMAND = "TEST_REPLAY_NOP_COMMAND"
TEST_DYNAMIC_REQUEST_COMMAND = "TEST_DYNAMIC_REQUEST_COMMAND"
TEST_DYNAMIC_REQUEST_DECISION = "TEST_DYNAMIC_REQUEST_DECISION"


def _build_game() -> tuple[Game, Player]:
    player = Player("P1")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player])
    game.turn = 1
    return game, player


def _queue_confirmation(game: Game, player: Player) -> DecisionRequest:
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    return request


def _resolve_option(game: Game, request: DecisionRequest, *, option_index: int) -> None:
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=request.options[int(option_index)].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert bool(getattr(apply_result, "ok", False))


def _canonical_snapshot(snapshot: dict) -> str:
    payload = dict(snapshot or {})
    payload.pop("events", None)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _register_test_replay_nop_command() -> None:
    if TEST_REPLAY_NOP_COMMAND in command_dispatcher._HANDLERS:
        return
    register_command_handler(
        TEST_REPLAY_NOP_COMMAND,
        validate=lambda _game, _command: (),
        apply=lambda game, _command: setattr(game, "battle_round", int(getattr(game, "battle_round", 0) or 0) + 1),
    )


def _register_test_dynamic_request_handlers() -> None:
    if TEST_DYNAMIC_REQUEST_DECISION not in decision_dispatcher._HANDLERS:
        register_decision_handler(
            TEST_DYNAMIC_REQUEST_DECISION,
            validate=_validate_test_dynamic_request_decision,
            apply=_apply_test_dynamic_request_decision,
        )
    if TEST_DYNAMIC_REQUEST_COMMAND in command_dispatcher._HANDLERS:
        return
    register_command_handler(
        TEST_DYNAMIC_REQUEST_COMMAND,
        validate=lambda _game, _command: (),
        apply=_apply_test_dynamic_request_command,
    )


def _apply_test_dynamic_request_command(game: Game, command: GameCommand) -> DecisionRequest:
    primary_id = str(uuid.uuid4())
    setattr(game, "_test_dynamic_entities", {"primary": primary_id})
    request = DecisionRequest.create(
        TEST_DYNAMIC_REQUEST_DECISION,
        "Pick dynamic entity",
        player_id=command.player_id,
        options=[
            DecisionOption.create("Skip", payload={"entity_id": None}),
            DecisionOption.create("Pick primary", payload={"entity_id": primary_id}),
        ],
    )
    game.request_decision(request)
    return request


def _validate_test_dynamic_request_decision(game: Game, request: DecisionRequest, result: DecisionResult):
    selected_option = next(
        (option for option in list(getattr(request, "options", []) or []) if option.option_id == result.option_id),
        None,
    )
    if selected_option is None:
        return ("Selected option is missing.",)
    entity_id = dict(getattr(selected_option, "payload", {}) or {}).get("entity_id", None)
    if entity_id is None:
        return ()
    entities = dict(getattr(game, "_test_dynamic_entities", {}) or {})
    if entity_id not in set(entities.values()):
        return ("Dynamic entity not found.",)
    return ()


def _apply_test_dynamic_request_decision(game: Game, request: DecisionRequest, result: DecisionResult) -> str | None:
    selected_option = next(
        (option for option in list(getattr(request, "options", []) or []) if option.option_id == result.option_id),
        None,
    )
    if selected_option is None:
        return None
    entity_id = dict(getattr(selected_option, "payload", {}) or {}).get("entity_id", None)
    setattr(game, "_test_dynamic_choice", entity_id)
    return entity_id


def test_replay_store_records_decisions_events_and_keyframes(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "pvp_match.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=1,
        session_id="session-1",
        label="PvP Match",
    )
    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1
    assert reader.keyframe_count() >= 2

    steps = reader.list_steps(limit=10)
    assert len(steps) == 1
    step = steps[0]
    assert step.decision_idx == 1
    assert step.decision_type == DECISION_CONFIRM_YES_NO
    assert step.actor_player_id == str(player.id)
    assert step.controller_kind in ("human_local", "human_remote", "ai", "unknown")

    record = reader.get_decision_record(1)
    assert str(record.get("decision_id", "")) == str(request.decision_id)
    assert str(record.get("decision_type", "")) == DECISION_CONFIRM_YES_NO

    request_payload = reader.get_request_payload(1)
    assert str(request_payload.get("decision_id", "")) == str(request.decision_id)
    assert str(request_payload.get("prompt", "")) == "Confirm?"
    assert [str(option.get("label", "") or "") for option in list(request_payload.get("options", []) or [])] == [
        "Yes",
        "No",
    ]

    events = reader.get_events_for_decision(1)
    event_types = {str(entry.get("type", "") or "") for entry in events}
    assert "decision_requested" in event_types
    assert "decision_resolved" in event_types


def test_pack_json_normalizes_dice_roll_state_objects() -> None:
    state = DiceRollState(
        roll_id=7,
        player_id="player-1",
        spec={"reason": "advance_roll"},
        status="resolved",
        total=6,
        final=True,
    )

    unpacked = dict(_unpack_json(_pack_json({"roll_state": state})))

    assert dict(unpacked["roll_state"]) == {
        "created_at": float(state.created_at),
        "dice": [],
        "final": True,
        "per_die_success": {},
        "player_id": "player-1",
        "reroll_history": [],
        "reroll_options": [],
        "resolved_at": None,
        "roll_id": 7,
        "sorted_ids": [],
        "spec": {"reason": "advance_roll"},
        "status": "resolved",
        "sum_success": None,
        "total": 6,
    }


def test_replay_store_reconstructs_state_at_decision_idx(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "reconstruct.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-2",
        label="Replay Reconstruction",
    )

    first = _queue_confirmation(game, player)
    _resolve_option(game, first, option_index=0)
    expected_after_first = game.save_snapshot()

    second = _queue_confirmation(game, player)
    _resolve_option(game, second, option_index=1)

    reader = ReplayStoreReader(replay_path)
    replayed_game = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_snapshot = replayed_game.save_snapshot()

    assert _canonical_snapshot(replayed_snapshot) == _canonical_snapshot(expected_after_first)


def test_replay_store_keyframe_is_captured_after_followups(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "post_settled.replay.sqlite3"
    starting_turn = int(game.turn)

    def _apply_post_followup_side_effect(self, request, result) -> None:
        self.turn = int(self.turn) + 1

    game._maybe_apply_optional_ability_confirmation = MethodType(_apply_post_followup_side_effect, game)
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=1,
        session_id="session-3",
        label="Post Settled Keyframe",
    )
    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)
    expected_snapshot = game.save_snapshot()

    reader = ReplayStoreReader(replay_path)
    replayed_game = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_snapshot = replayed_game.save_snapshot()

    assert _canonical_snapshot(replayed_snapshot) == _canonical_snapshot(expected_snapshot)
    assert int(replayed_game.turn) == starting_turn + 1


def test_replay_store_reconstructs_steps_with_leading_command_events(tmp_path) -> None:
    _register_test_replay_nop_command()
    game, player = _build_game()
    replay_path = tmp_path / "leading_command.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-leading-command",
        label="Replay Leading Command",
    )

    game.apply_command(GameCommand.create(TEST_REPLAY_NOP_COMMAND, player_id=player.id))

    first = _queue_confirmation(game, player)
    first_cmd = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=player.id,
        payload={
            "decision_id": first.decision_id,
            "option_id": first.options[0].option_id,
            "result_payload": {},
        },
    )
    first_result = game.apply_command(first_cmd)
    assert bool(getattr(first_result, "ok", False))
    expected_after_first = game.save_snapshot()

    second = _queue_confirmation(game, player)
    _resolve_option(game, second, option_index=1)
    expected_after_second = game.save_snapshot()

    reader = ReplayStoreReader(replay_path)
    first_events = reader.get_events_for_decision(1)
    second_events = reader.get_events_for_decision(2)

    assert [str(entry.get("type", "") or "") for entry in first_events[:3]] == [
        "command_applied",
        "decision_requested",
        "decision_resolved",
    ]
    assert [str(entry.get("type", "") or "") for entry in second_events[:3]] == [
        "command_applied",
        "decision_requested",
        "decision_resolved",
    ]

    replayed_after_first = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_after_second = reader.reconstruct_game_at_decision(2, strict=True)

    assert _canonical_snapshot(replayed_after_first.save_snapshot()) == _canonical_snapshot(expected_after_first)
    assert _canonical_snapshot(replayed_after_second.save_snapshot()) == _canonical_snapshot(expected_after_second)


def test_replay_store_reconstructs_steps_with_leading_dice_roll_events(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "leading_dice_roll.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-leading-dice-roll",
        label="Replay Leading Dice Roll",
    )

    with game_context(game):
        _ = dice_mod.get_dice_roll(6)

    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)
    expected_snapshot = game.save_snapshot()

    reader = ReplayStoreReader(replay_path)
    events = reader.get_events_for_decision(1)
    assert [str(entry.get("type", "") or "") for entry in events[:3]] == [
        "dice_roll",
        "decision_requested",
        "decision_resolved",
    ]

    replayed_game = reader.reconstruct_game_at_decision(1, strict=True)
    assert _canonical_snapshot(replayed_game.save_snapshot()) == _canonical_snapshot(expected_snapshot)


def test_enable_decision_replay_recording_is_idempotent(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "idempotent.replay.sqlite3"

    enable_decision_replay_recording(game, replay_path=replay_path, session_id="session-4")
    enable_decision_replay_recording(game, replay_path=replay_path, session_id="session-4")

    listeners = [
        group
        for _callback, group in list(getattr(game.event_system, "subscribers", {}).get("decision_settled", []))
        if str(group) == REPLAY_RECORDING_GROUP
    ]
    assert len(listeners) == 1

    request = _queue_confirmation(game, player)
    _resolve_option(game, request, option_index=0)

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1


def test_request_payload_for_runtime_remaps_unit_and_model_ids() -> None:
    runtime_models = [
        SimpleNamespace(id="runtime-model-1"),
        SimpleNamespace(id="runtime-model-2"),
    ]
    runtime_unit = SimpleNamespace(id="runtime-unit-1", name="Bloodletters", models=runtime_models)
    runtime_army = SimpleNamespace(units=[runtime_unit])
    runtime_player = SimpleNamespace(id="player-1", army=runtime_army)
    runtime_game = SimpleNamespace(players=[runtime_player], entity_registry=SimpleNamespace(get=lambda entity_id, kind=None: runtime_unit if entity_id == "runtime-unit-1" and kind == "unit" else None))

    payload = {
        "context": {"unit_id": "recorded-unit-1"},
        "options": [
            {
                "label": "Place",
                "payload": {
                    "unit_id": "recorded-unit-1",
                    "model_positions": [
                        {"model_id": "recorded-model-1", "position": [1.0, 2.0, 0.0]},
                        {"model_id": "recorded-model-2", "position": [3.0, 4.0, 0.0]},
                    ],
                },
            }
        ],
    }
    record = {
        "omniscient_state": {
            "units": [
                {"name": "Bloodletters", "owner_player_id": "player-1", "unit_id": "recorded-unit-1"},
            ]
        }
    }

    translated = ReplayStoreReader._request_payload_for_runtime(runtime_game, payload, record)

    assert translated["context"]["unit_id"] == "runtime-unit-1"
    assert translated["options"][0]["payload"]["unit_id"] == "runtime-unit-1"
    assert translated["options"][0]["payload"]["model_positions"] == [
        {"model_id": "runtime-model-1", "position": [1.0, 2.0, 0.0]},
        {"model_id": "runtime-model-2", "position": [3.0, 4.0, 0.0]},
    ]


def test_replay_store_matches_runtime_request_when_recorded_ids_drift(tmp_path, caplog) -> None:
    _register_test_dynamic_request_handlers()
    game, player = _build_game()
    replay_path = tmp_path / "dynamic_request.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-dynamic-request",
        label="Replay Dynamic Request",
    )

    result = game.apply_command(GameCommand.create(TEST_DYNAMIC_REQUEST_COMMAND, player_id=player.id))
    assert bool(getattr(result, "ok", False))
    request = game.decision_queue.peek()
    assert request is not None
    _resolve_option(game, request, option_index=1)

    reader = ReplayStoreReader(replay_path)
    recorded_request = reader.get_request_payload(1)
    recorded_primary_id = next(
        (
            dict(option.get("payload", {}) or {}).get("entity_id", None)
            for option in list(recorded_request.get("options", []) or [])
            if str(option.get("label", "") or "") == "Pick primary"
        ),
        None,
    )
    assert recorded_primary_id

    with caplog.at_level(logging.ERROR):
        replayed_game = reader.reconstruct_game_at_decision(1, strict=True)

    assert getattr(replayed_game, "event_log", None) is None
    assert "Expected event 'decision_requested', got 'command_applied'." not in caplog.text
    replayed_choice = getattr(replayed_game, "_test_dynamic_choice", None)
    replayed_entities = dict(getattr(replayed_game, "_test_dynamic_entities", {}) or {})
    assert replayed_choice == replayed_entities.get("primary")
    assert replayed_choice != recorded_primary_id
