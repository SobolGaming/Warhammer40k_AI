from __future__ import annotations

import json
import logging
import sqlite3
from types import MethodType, SimpleNamespace
import uuid

from warhammer40k_ai.engine import command_dispatcher
from warhammer40k_ai.engine import decision_dispatcher
from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.command_dispatcher import register_command_handler
from warhammer40k_ai.engine.command_kinds import CMD_RESOLVE_DECISION
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_dispatcher import register_decision_handler
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CONFIRM_YES_NO,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.dice_rolls import DiceRollState
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.missions import DeploymentZone, DeploymentZoneType
from warhammer40k_ai.engine.phase import BattleRoundPhases
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
TEST_ZONE_DEPENDENT_DECISION = "TEST_ZONE_DEPENDENT_DECISION"
TEST_CHAINED_OUTER_DECISION = "TEST_CHAINED_OUTER_DECISION"
TEST_CHAINED_INNER_DECISION = "TEST_CHAINED_INNER_DECISION"
TEST_REENTRANT_OUTER_DECISION = "TEST_REENTRANT_OUTER_DECISION"
TEST_REENTRANT_INNER_DECISION = "TEST_REENTRANT_INNER_DECISION"
TEST_REENTRANT_DICE_DECISION = "TEST_REENTRANT_DICE_DECISION"


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


def test_reader_decision_row_count_distinguishes_autoincrement_gaps(tmp_path):
    replay_path = tmp_path / "replay.sqlite3"
    with sqlite3.connect(replay_path) as conn:
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
        conn.execute(
            """
            CREATE TABLE decision_steps (
                decision_idx INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT NOT NULL UNIQUE
            )
            """
        )
        conn.execute("INSERT INTO decision_steps(decision_idx, decision_id) VALUES(1, 'a')")
        conn.execute("INSERT INTO decision_steps(decision_idx, decision_id) VALUES(3, 'b')")

    reader = ReplayStoreReader(replay_path)

    assert reader.decision_count() == 3
    assert reader.decision_row_count() == 2


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


def _register_test_zone_dependent_handler() -> None:
    if TEST_ZONE_DEPENDENT_DECISION in decision_dispatcher._HANDLERS:
        return
    register_decision_handler(
        TEST_ZONE_DEPENDENT_DECISION,
        validate=_validate_test_zone_dependent_decision,
        apply=lambda _game, _request, _result: True,
    )


def _register_test_chained_decision_handlers() -> None:
    if TEST_CHAINED_OUTER_DECISION not in decision_dispatcher._HANDLERS:
        register_decision_handler(
            TEST_CHAINED_OUTER_DECISION,
            validate=_validate_test_chained_outer_decision,
            apply=_apply_test_chained_outer_decision,
        )
    if TEST_CHAINED_INNER_DECISION in decision_dispatcher._HANDLERS:
        return
    register_decision_handler(
        TEST_CHAINED_INNER_DECISION,
        validate=_validate_test_chained_inner_decision,
        apply=_apply_test_chained_inner_decision,
    )


def _register_test_reentrant_decision_handlers() -> None:
    if TEST_REENTRANT_OUTER_DECISION not in decision_dispatcher._HANDLERS:
        register_decision_handler(
            TEST_REENTRANT_OUTER_DECISION,
            validate=lambda _game, _request, _result: (),
            apply=_apply_test_reentrant_outer_decision,
        )
    if TEST_REENTRANT_INNER_DECISION in decision_dispatcher._HANDLERS:
        return
    register_decision_handler(
        TEST_REENTRANT_INNER_DECISION,
        validate=_validate_test_reentrant_inner_decision,
        apply=_apply_test_reentrant_inner_decision,
    )


def _register_test_reentrant_dice_decision_handler() -> None:
    if TEST_REENTRANT_DICE_DECISION in decision_dispatcher._HANDLERS:
        return
    register_decision_handler(
        TEST_REENTRANT_DICE_DECISION,
        validate=lambda _game, _request, _result: (),
        apply=_apply_test_reentrant_dice_decision,
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


def _validate_test_zone_dependent_decision(game: Game, request: DecisionRequest, result: DecisionResult):
    selected_option = next(
        (option for option in list(getattr(request, "options", []) or []) if option.option_id == result.option_id),
        None,
    )
    if selected_option is None:
        return ("Selected option is missing.",)
    player_id = str(getattr(request, "player_id", None) or getattr(result, "player_id", None) or "")
    zone = dict(getattr(game, "deployment_zones", {}).get(player_id, {}) or {})
    if str(zone.get("zone_type", "") or "") != str(request.context.get("expected_zone_type", "") or ""):
        return ("Unexpected deployment zone type.",)
    if str(zone.get("name", "") or "") != str(request.context.get("expected_zone_name", "") or ""):
        return ("Unexpected deployment zone name.",)
    return ()


def _validate_test_chained_outer_decision(game: Game, _request: DecisionRequest, _result: DecisionResult):
    if bool(getattr(game, "_test_nested_inner_resolved", False)):
        return ("Outer decision cannot resolve after nested follow-up.",)
    return ()


def _apply_test_chained_outer_decision(game: Game, request: DecisionRequest, _result: DecisionResult) -> bool:
    setattr(game, "_test_nested_outer_resolved", True)
    return True


def _validate_test_chained_inner_decision(game: Game, _request: DecisionRequest, _result: DecisionResult):
    if not bool(getattr(game, "_test_nested_outer_resolved", False)):
        return ("Nested follow-up requires the outer decision first.",)
    if bool(getattr(game, "_test_nested_inner_resolved", False)):
        return ("Nested follow-up already resolved.",)
    return ()


def _apply_test_chained_inner_decision(game: Game, _request: DecisionRequest, _result: DecisionResult) -> bool:
    setattr(game, "_test_nested_inner_resolved", True)
    return True


def _apply_test_reentrant_outer_decision(game: Game, request: DecisionRequest, _result: DecisionResult) -> bool:
    game.turn = int(getattr(game, "turn", 0) or 0) + 1
    setattr(game, "_test_reentrant_outer_resolved", True)
    inner = DecisionRequest.create(
        TEST_REENTRANT_INNER_DECISION,
        "Resolve reentrant follow-up",
        player_id=request.player_id,
        options=[DecisionOption.create("Continue", payload={})],
    )
    game.request_decision(inner)
    return True


def _validate_test_reentrant_inner_decision(game: Game, _request: DecisionRequest, _result: DecisionResult):
    if not bool(getattr(game, "_test_reentrant_outer_resolved", False)):
        return ("Reentrant follow-up requires the outer decision first.",)
    return ()


def _apply_test_reentrant_inner_decision(game: Game, _request: DecisionRequest, _result: DecisionResult) -> bool:
    game.turn = int(getattr(game, "turn", 0) or 0) + 10
    setattr(game, "_test_reentrant_inner_resolved", True)
    return True


def _apply_test_reentrant_dice_decision(game: Game, request: DecisionRequest, _result: DecisionResult) -> bool:
    value = dice_mod.get_roll(
        "D6",
        player_id=request.player_id,
        reason="Nested replay test roll",
        roll_type="test",
    )
    setattr(game, "_test_reentrant_roll_value", int(value))
    return True


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


def test_replay_store_record_resolution_is_idempotent_by_decision_id(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "idempotent_decision.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-idempotent",
        label="Idempotent Replay",
    )
    request = _queue_confirmation(game, player)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=request.player_id,
        option_id=request.options[0].option_id,
        payload={},
    )
    apply_result = game.resolve_decision(result)
    assert bool(getattr(apply_result, "ok", False))

    recorder = getattr(game, "_decision_replay_recorder")
    recorder.record_resolution(game, request, result)

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1
    step = reader.get_step(1)
    assert step.decision_id == request.decision_id
    assert step.event_start_id is not None
    assert step.event_end_id is not None
    assert step.event_end_id >= step.event_start_id


def test_replay_store_decision_count_uses_max_index_when_autoincrement_has_gap(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "gapped_decision_idx.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-gapped-index",
        label="Gapped Replay Index",
    )
    first = _queue_confirmation(game, player)
    _resolve_option(game, first, option_index=0)

    with sqlite3.connect(str(replay_path)) as conn:
        conn.execute("UPDATE sqlite_sequence SET seq = 2 WHERE name = 'decision_steps'")

    second = _queue_confirmation(game, player)
    _resolve_option(game, second, option_index=1)

    reader = ReplayStoreReader(replay_path)
    steps = reader.list_steps(limit=10)
    assert [step.decision_idx for step in steps] == [1, 3]
    assert reader.decision_count() == 3
    assert reader.get_step(3).decision_id == second.decision_id
    try:
        reader.get_step(2)
    except IndexError:
        pass
    else:
        raise AssertionError("missing decision_idx=2 should not resolve by ordinal offset")

    reader.reconstruct_game_at_decision(reader.decision_count(), strict=True)


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


def test_replay_store_reconstruction_syncs_returned_game_to_step_phase(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "phase_start_sync.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-phase-start-sync",
        label="Replay Phase Start Sync",
    )

    first = _queue_confirmation(game, player)
    _resolve_option(game, first, option_index=0)

    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.event_system.publish("phase_start", player=player, phase=game.phase)
    second = _queue_confirmation(game, player)
    _resolve_option(game, second, option_index=1)

    reader = ReplayStoreReader(replay_path)
    replayed_game = reader.reconstruct_game_at_decision(2, strict=True)

    assert reader.get_step(2).phase == "MOVEMENT_PHASE"
    assert replayed_game.phase == BattleRoundPhases.MOVEMENT_PHASE
    assert int(replayed_game.current_player_index) == 0


def test_replay_store_keyframe_excludes_post_resolved_followups(tmp_path) -> None:
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

    assert int(game.turn) == starting_turn + 1
    assert _canonical_snapshot(replayed_game.save_snapshot()) != _canonical_snapshot(expected_snapshot)
    assert int(replayed_game.turn) == starting_turn


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
        "decision_requested",
        "decision_resolved",
        "command_applied",
    ]
    assert [str(entry.get("type", "") or "") for entry in second_events[:2]] == [
        "decision_requested",
        "decision_resolved",
    ]
    assert first_events[-1]["payload"]["kind"] == CMD_RESOLVE_DECISION
    assert first_events[-1]["payload"]["payload"]["decision_id"] == first.decision_id
    assert all(
        str(dict(entry.get("payload", {}) or {}).get("kind", "") or "") != TEST_REPLAY_NOP_COMMAND
        for entry in first_events
    )

    replayed_after_first = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_after_second = reader.reconstruct_game_at_decision(2, strict=True)

    assert _canonical_snapshot(replayed_after_first.save_snapshot()) == _canonical_snapshot(expected_after_first)
    assert _canonical_snapshot(replayed_after_second.save_snapshot()) == _canonical_snapshot(expected_after_second)


def test_replay_store_persists_trailing_resolve_command_for_final_decision(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "final_resolve_command.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-final-resolve-command",
        label="Replay Final Resolve Command",
    )

    request = _queue_confirmation(game, player)
    result = game.apply_command(
        GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=player.id,
            payload={
                "decision_id": request.decision_id,
                "option_id": request.options[0].option_id,
                "result_payload": {},
            },
        )
    )
    assert bool(getattr(result, "ok", False))

    reader = ReplayStoreReader(replay_path)
    step = reader.get_step(1)
    events = reader.get_events_for_decision(1)

    assert step.event_end_id is not None
    assert [str(entry.get("type", "") or "") for entry in events] == [
        "decision_requested",
        "decision_resolved",
        "command_applied",
    ]
    assert events[-1]["event_id"] == step.event_end_id
    assert events[-1]["payload"]["kind"] == CMD_RESOLVE_DECISION
    assert events[-1]["payload"]["payload"]["decision_id"] == request.decision_id


def test_replay_store_flushes_current_command_before_post_command_followups(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "post_command_followup.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-post-command-followup",
        label="Replay Post Command Followup",
    )

    followup_state: dict[str, str | bool] = {"queued": False, "decision_id": ""}

    def _queue_post_command_followup(self, command, result) -> bool:
        if bool(followup_state["queued"]):
            return False
        if str(getattr(command, "kind", "") or "") != CMD_RESOLVE_DECISION:
            return False
        if not bool(getattr(result, "ok", False)):
            return False
        followup_state["queued"] = True
        followup = DecisionRequest.create(
            DECISION_CONFIRM_YES_NO,
            "Resolve follow-up?",
            player_id=player.id,
            options=[
                DecisionOption.create("Yes", payload={"choice": True}),
                DecisionOption.create("No", payload={"choice": False}),
            ],
        )
        followup_state["decision_id"] = str(followup.decision_id)
        self.request_decision(followup)
        followup_result = self.apply_command(
            GameCommand.create(
                CMD_RESOLVE_DECISION,
                player_id=player.id,
                payload={
                    "decision_id": followup.decision_id,
                    "option_id": followup.options[0].option_id,
                    "result_payload": {},
                },
            )
        )
        assert bool(getattr(followup_result, "ok", False))
        return True

    game._maybe_queue_post_command_tool_decisions = MethodType(_queue_post_command_followup, game)

    request = _queue_confirmation(game, player)
    result = game.apply_command(
        GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=player.id,
            payload={
                "decision_id": request.decision_id,
                "option_id": request.options[0].option_id,
                "result_payload": {},
            },
        )
    )
    assert bool(getattr(result, "ok", False))

    reader = ReplayStoreReader(replay_path)
    steps = reader.list_steps(limit=10)
    assert [step.decision_type for step in steps] == [
        DECISION_CONFIRM_YES_NO,
        DECISION_CONFIRM_YES_NO,
    ]
    assert steps[0].event_end_id is not None
    assert steps[1].event_start_id is not None
    assert int(steps[0].event_end_id) < int(steps[1].event_start_id)

    first_events = reader.get_events_for_decision(1)
    second_events = reader.get_events_for_decision(2)

    assert [str(entry.get("type", "") or "") for entry in first_events] == [
        "decision_requested",
        "decision_resolved",
        "command_applied",
    ]
    assert [str(entry.get("type", "") or "") for entry in second_events] == [
        "decision_requested",
        "decision_resolved",
        "command_applied",
    ]
    assert first_events[-1]["payload"]["payload"]["decision_id"] == request.decision_id
    assert second_events[-1]["payload"]["payload"]["decision_id"] == str(followup_state["decision_id"] or "")


def test_replay_store_preserves_nested_decision_order_for_strict_replay(tmp_path) -> None:
    _register_test_chained_decision_handlers()
    game, player = _build_game()
    replay_path = tmp_path / "nested_decision_order.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-nested-order",
        label="Replay Nested Decision Order",
    )

    def _queue_nested_followup(self, request, _result) -> None:
        if str(getattr(request, "decision_type", "") or "") != TEST_CHAINED_OUTER_DECISION:
            return
        followup = DecisionRequest.create(
            TEST_CHAINED_INNER_DECISION,
            "Resolve follow-up",
            player_id=request.player_id,
            options=[DecisionOption.create("Continue", payload={})],
        )
        self.request_decision(followup)

    game._maybe_apply_choice_samples_followup = MethodType(_queue_nested_followup, game)

    def _auto_resolve_nested_followup(*, request=None, game=None, **_kwargs) -> None:
        if request is None or game is None:
            return
        if str(getattr(request, "decision_type", "") or "") != TEST_CHAINED_INNER_DECISION:
            return
        cmd = GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=request.player_id,
            payload={
                "decision_id": request.decision_id,
                "option_id": request.options[0].option_id,
                "result_payload": {},
            },
        )
        result = game.apply_command(cmd)
        assert bool(getattr(result, "ok", False))

    game.event_system.subscribe_group("test_nested_auto", "decision_requested", _auto_resolve_nested_followup)

    outer = DecisionRequest.create(
        TEST_CHAINED_OUTER_DECISION,
        "Choose outer action",
        player_id=player.id,
        options=[DecisionOption.create("Continue", payload={})],
    )
    game.request_decision(outer)
    outer_result = game.apply_command(
        GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=player.id,
            payload={
                "decision_id": outer.decision_id,
                "option_id": outer.options[0].option_id,
                "result_payload": {},
            },
        )
    )
    assert bool(getattr(outer_result, "ok", False))

    reader = ReplayStoreReader(replay_path)
    steps = reader.list_steps(limit=10)

    assert [step.decision_type for step in steps] == [
        TEST_CHAINED_OUTER_DECISION,
        TEST_CHAINED_INNER_DECISION,
    ]

    replayed_game = reader.reconstruct_game_at_decision(2, strict=True)
    assert bool(getattr(replayed_game, "_test_nested_outer_resolved", False))
    assert bool(getattr(replayed_game, "_test_nested_inner_resolved", False))


def test_replay_store_preserves_request_order_for_reentrant_auto_resolved_decision(tmp_path) -> None:
    _register_test_reentrant_decision_handlers()
    game, player = _build_game()
    replay_path = tmp_path / "reentrant_decision_order.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-reentrant-order",
        label="Replay Reentrant Decision Order",
    )

    def _auto_resolve_reentrant_followup(*, request=None, game=None, **_kwargs) -> None:
        if request is None or game is None:
            return
        if str(getattr(request, "decision_type", "") or "") != TEST_REENTRANT_INNER_DECISION:
            return
        result = game.apply_command(
            GameCommand.create(
                CMD_RESOLVE_DECISION,
                player_id=request.player_id,
                payload={
                    "decision_id": request.decision_id,
                    "option_id": request.options[0].option_id,
                    "result_payload": {},
                },
            )
        )
        assert bool(getattr(result, "ok", False))

    game.event_system.subscribe_group("test_reentrant_auto", "decision_requested", _auto_resolve_reentrant_followup)

    outer = DecisionRequest.create(
        TEST_REENTRANT_OUTER_DECISION,
        "Choose reentrant outer action",
        player_id=player.id,
        options=[DecisionOption.create("Continue", payload={})],
    )
    game.request_decision(outer)
    outer_result = game.apply_command(
        GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=player.id,
            payload={
                "decision_id": outer.decision_id,
                "option_id": outer.options[0].option_id,
                "result_payload": {},
            },
        )
    )
    assert bool(getattr(outer_result, "ok", False))

    reader = ReplayStoreReader(replay_path)
    steps = reader.list_steps(limit=10)

    assert [step.decision_type for step in steps] == [
        TEST_REENTRANT_OUTER_DECISION,
        TEST_REENTRANT_INNER_DECISION,
    ]

    replayed_game = reader.reconstruct_game_at_decision(2, strict=True)
    assert bool(getattr(replayed_game, "_test_reentrant_outer_resolved", False))
    assert bool(getattr(replayed_game, "_test_reentrant_inner_resolved", False))


def test_replay_keyframe_excludes_controller_drained_followup_decision(tmp_path) -> None:
    _register_test_reentrant_decision_handlers()
    game, player = _build_game()
    replay_path = tmp_path / "reentrant_controller_keyframe.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=1,
        session_id="session-reentrant-controller-keyframe",
        label="Replay Reentrant Controller Keyframe",
    )
    starting_turn = int(game.turn)

    class DeferredFollowupController:
        def handles_player(self, _player_id) -> bool:
            return True

        def on_decision_requested(self, _game, _request) -> None:
            return None

        def on_decision_resolved(self, game, _request, _result) -> None:
            pending = game.decision_queue.peek()
            if pending is None:
                return
            if str(getattr(pending, "decision_type", "") or "") != TEST_REENTRANT_INNER_DECISION:
                return
            result = game.apply_command(
                GameCommand.create(
                    CMD_RESOLVE_DECISION,
                    player_id=pending.player_id,
                    payload={
                        "decision_id": pending.decision_id,
                        "option_id": pending.options[0].option_id,
                        "result_payload": {},
                    },
                )
            )
            assert bool(getattr(result, "ok", False))

    game.add_decision_controller(DeferredFollowupController())

    outer = DecisionRequest.create(
        TEST_REENTRANT_OUTER_DECISION,
        "Choose reentrant outer action",
        player_id=player.id,
        options=[DecisionOption.create("Continue", payload={})],
    )
    game.request_decision(outer)
    outer_result = game.apply_command(
        GameCommand.create(
            CMD_RESOLVE_DECISION,
            player_id=player.id,
            payload={
                "decision_id": outer.decision_id,
                "option_id": outer.options[0].option_id,
                "result_payload": {},
            },
        )
    )
    assert bool(getattr(outer_result, "ok", False))
    assert int(game.turn) == starting_turn + 11

    reader = ReplayStoreReader(replay_path)
    steps = reader.list_steps(limit=10)
    assert [step.decision_type for step in steps] == [
        TEST_REENTRANT_OUTER_DECISION,
        TEST_REENTRANT_INNER_DECISION,
    ]

    replayed_after_outer = reader.reconstruct_game_at_decision(1, strict=True)
    replayed_after_inner = reader.reconstruct_game_at_decision(2, strict=True)

    assert int(replayed_after_outer.turn) == starting_turn + 1
    assert int(replayed_after_inner.turn) == starting_turn + 11


def test_replay_reconstruction_uses_recorded_dice_for_reentrant_rolls(tmp_path) -> None:
    _register_test_reentrant_dice_decision_handler()
    game, player = _build_game()
    replay_path = tmp_path / "reentrant_dice_results.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-reentrant-dice-results",
        label="Replay Reentrant Dice Results",
    )

    request = DecisionRequest.create(
        TEST_REENTRANT_DICE_DECISION,
        "Resolve reentrant dice action",
        player_id=player.id,
        options=[DecisionOption.create("Continue", payload={})],
    )
    game.request_decision(request)
    result = game.resolve_decision(
        DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=request.options[0].option_id,
            payload={},
        )
    )
    assert bool(getattr(result, "ok", False))

    reader = ReplayStoreReader(replay_path)
    steps = reader.list_steps(limit=10)
    assert [step.decision_type for step in steps] == [
        TEST_REENTRANT_DICE_DECISION,
        DECISION_REQUEST_DICE_ROLL,
    ]
    dice_step = steps[1]
    dice_record = reader.get_decision_record(dice_step.decision_idx)
    roll_value = ((dice_record["outcome"]["immediate_deltas"]["value"]["dice"])[0])
    roll_value["value"] = 6
    roll_value["raw_value"] = 6
    dice_record["outcome"]["immediate_deltas"]["value"]["total"] = 6
    with sqlite3.connect(replay_path) as conn:
        conn.execute(
            "UPDATE decision_steps SET decision_record_blob = ? WHERE decision_idx = ?",
            (_pack_json(dice_record), int(dice_step.decision_idx)),
        )

    replayed_game = reader.reconstruct_game_at_decision(2, strict=True)

    assert int(getattr(replayed_game, "_test_reentrant_roll_value", 0) or 0) == 6


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


def test_replay_store_reapplies_recorded_deployment_zone_ownership(tmp_path) -> None:
    _register_test_zone_dependent_handler()
    player1 = Player("P1")
    player2 = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player1, player2])
    game.turn = 1
    attacker_zone = DeploymentZone(
        name="Attacker Zone",
        zone_type=DeploymentZoneType.ATTACKER,
        vertices=[(30.0, 0.0), (60.0, 0.0), (60.0, 22.0), (30.0, 22.0)],
    )
    defender_zone = DeploymentZone(
        name="Defender Zone",
        zone_type=DeploymentZoneType.DEFENDER,
        vertices=[(0.0, 22.0), (30.0, 22.0), (30.0, 44.0), (0.0, 44.0)],
    )
    game.deployment_zones = {
        player1.id: {"name": "Attacker Zone", "zone_type": "attacker", "mission_zones": [attacker_zone]},
        player2.id: {"name": "Defender Zone", "zone_type": "defender", "mission_zones": [defender_zone]},
    }
    replay_path = tmp_path / "deployment_zone_assignment.replay.sqlite3"
    enable_decision_replay_recording(
        game,
        replay_path=replay_path,
        keyframe_interval=25,
        session_id="session-zone-assignment",
        label="Replay Deployment Zone Assignment",
    )

    zone_choice_context = {
        "available_zone_choice_ids": ["zone:player2", "zone:player1"],
        "available_zone_keys": ["zone:player2", "zone:player1"],
        "available_zone_choices": [
            {
                "zone_choice_id": "zone:player2",
                "zone_key": "zone:player2",
                "zone_name": "Player 2's Zone",
                "zone_type": "attacker",
                "zone_index": 1,
            },
            {
                "zone_choice_id": "zone:player1",
                "zone_key": "zone:player1",
                "zone_name": "Player 1's Zone",
                "zone_type": "defender",
                "zone_index": 0,
            },
        ],
    }
    zone_request = DecisionRequest.create(
        DECISION_CHOOSE_DEPLOYMENT_ZONE,
        "Choose deployment zone.",
        player_id=player2.id,
        options=[
            DecisionOption.create(
                "Player 2's Zone",
                payload={
                    "zone_choice_id": "zone:player2",
                    "zone_key": "zone:player2",
                    "zone_name": "Player 2's Zone",
                    "zone_type": "attacker",
                    "zone_index": 1,
                },
            ),
            DecisionOption.create(
                "Player 1's Zone",
                payload={
                    "zone_choice_id": "zone:player1",
                    "zone_key": "zone:player1",
                    "zone_name": "Player 1's Zone",
                    "zone_type": "defender",
                    "zone_index": 0,
                },
            ),
        ],
        context=zone_choice_context,
    )
    game.decision_queue.add(zone_request)
    game.event_system.publish("decision_requested", request=zone_request, game=game)
    _resolve_option(game, zone_request, option_index=0)

    game.deployment_zones = {
        player2.id: {"name": "Player 2's Zone", "zone_type": "attacker", "mission_zones": [attacker_zone]},
        player1.id: {"name": "Player 1's Zone", "zone_type": "defender", "mission_zones": [defender_zone]},
    }
    game.defender_index = 1
    game.attacker_index = 0
    game.deployment_turn_index = 1
    game.current_player_index = 1

    validation_request = DecisionRequest.create(
        TEST_ZONE_DEPENDENT_DECISION,
        "Check deployment zone ownership.",
        player_id=player2.id,
        options=[DecisionOption.create("Continue", payload={})],
        context={"expected_zone_name": "Player 2's Zone", "expected_zone_type": "attacker"},
    )
    game.decision_queue.add(validation_request)
    game.event_system.publish("decision_requested", request=validation_request, game=game)
    _resolve_option(game, validation_request, option_index=0)

    reader = ReplayStoreReader(replay_path)
    replayed_game = reader.reconstruct_game_at_decision(2, strict=True)

    assert replayed_game.deployment_zones[player2.id]["name"] == "Player 2's Zone"
    assert replayed_game.deployment_zones[player2.id]["zone_type"] == "attacker"
    assert replayed_game.deployment_zones[player2.id]["mission_zones"][0].vertices == attacker_zone.vertices
    assert replayed_game.deployment_zones[player1.id]["name"] == "Player 1's Zone"
    assert replayed_game.deployment_zones[player1.id]["zone_type"] == "defender"
    assert replayed_game.deployment_zones[player1.id]["mission_zones"][0].vertices == defender_zone.vertices
    assert int(replayed_game.deployment_turn_index) == 1
    assert int(replayed_game.current_player_index) == 1


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


def test_replay_recording_backfills_accepted_settled_decision(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "settled_backfill.replay.sqlite3"
    enable_decision_replay_recording(game, replay_path=replay_path, session_id="session-settled-backfill")

    request = _queue_confirmation(game, player)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={"choice": True},
    )
    game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value={"choice": True},
    )

    game.event_system.publish(
        "decision_settled",
        request=request,
        result=result,
        game=game,
        accepted=True,
    )

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1
    assert reader.get_decision_record(1)["decision_id"] == request.decision_id


def test_decision_record_append_reserves_replay_step(tmp_path) -> None:
    game, player = _build_game()
    replay_path = tmp_path / "append_reserves_step.replay.sqlite3"
    enable_decision_replay_recording(game, replay_path=replay_path, session_id="session-append-reserve")

    request = _queue_confirmation(game, player)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={"choice": True},
    )
    game.decision_record_store.record_resolution(
        request,
        result,
        ok=True,
        errors=(),
        value={"choice": True},
    )

    reader = ReplayStoreReader(replay_path)
    assert reader.decision_count() == 1
    assert reader.get_decision_record(1)["decision_id"] == request.decision_id
    assert reader.get_request_payload(1)["decision_id"] == request.decision_id


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


def test_request_payload_for_runtime_uses_unit_disambiguators_for_duplicate_names() -> None:
    runtime_models_a = [
        SimpleNamespace(id="runtime-a-model-1", is_alive=True),
        SimpleNamespace(id="runtime-a-model-2", is_alive=True),
    ]
    runtime_models_b = [
        SimpleNamespace(id="runtime-b-model-1", is_alive=True),
        SimpleNamespace(id="runtime-b-model-2", is_alive=True),
        SimpleNamespace(id="runtime-b-model-3", is_alive=True),
    ]
    runtime_unit_a = SimpleNamespace(
        id="runtime-unit-a",
        name="Accursed Cultists",
        models=runtime_models_a,
        position=[30.0, 20.0, 0.0],
    )
    runtime_unit_b = SimpleNamespace(
        id="runtime-unit-b",
        name="Accursed Cultists",
        models=runtime_models_b,
        position=[5.0, 40.0, 0.0],
    )
    runtime_army = SimpleNamespace(units=[runtime_unit_b, runtime_unit_a])
    runtime_player = SimpleNamespace(id="player-1", army=runtime_army)
    registry_units = {
        runtime_unit_a.id: runtime_unit_a,
        runtime_unit_b.id: runtime_unit_b,
    }
    runtime_game = SimpleNamespace(
        players=[runtime_player],
        entity_registry=SimpleNamespace(
            get=lambda entity_id, kind=None: registry_units.get(entity_id) if kind == "unit" else None
        ),
    )

    payload = {
        "context": {"unit_id": "recorded-unit-a"},
        "options": [
            {
                "label": "Move",
                "payload": {
                    "unit_id": "recorded-unit-a",
                    "model_positions": [
                        {"model_id": "recorded-a-model-1", "position": [30.0, 20.0, 0.0]},
                        {"model_id": "recorded-a-model-2", "position": [31.0, 20.0, 0.0]},
                    ],
                },
            }
        ],
    }
    record = {
        "omniscient_state": {
            "units": [
                {
                    "name": "Accursed Cultists",
                    "owner_player_id": "player-1",
                    "unit_id": "recorded-unit-b",
                    "model_count": 3,
                    "alive_model_count": 3,
                    "position": [5.0, 40.0, 0.0],
                },
                {
                    "name": "Accursed Cultists",
                    "owner_player_id": "player-1",
                    "unit_id": "recorded-unit-a",
                    "model_count": 2,
                    "alive_model_count": 2,
                    "position": [30.0, 20.0, 0.0],
                },
            ]
        }
    }

    translated = ReplayStoreReader._request_payload_for_runtime(runtime_game, payload, record)

    assert translated["context"]["unit_id"] == "runtime-unit-a"
    assert translated["options"][0]["payload"]["unit_id"] == "runtime-unit-a"
    assert translated["options"][0]["payload"]["model_positions"] == [
        {"model_id": "runtime-a-model-1", "position": [30.0, 20.0, 0.0]},
        {"model_id": "runtime-a-model-2", "position": [31.0, 20.0, 0.0]},
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


def test_result_for_record_marks_skip_payload_for_skip_option() -> None:
    request = DecisionRequest.create(
        "MOVE_UNIT",
        "Move unit",
        player_id="player-1",
        options=[
            DecisionOption.create("Confirm", payload={"action": "confirm"}),
            DecisionOption.create("Skip", payload={"action": "skip"}),
        ],
    )
    skip_option_id = request.options[1].option_id
    action_id = request.action_id_for_option_id(skip_option_id)

    result = ReplayStoreReader._result_for_record(
        request,
        {
            "chosen_action_id": action_id,
            "human_action_injected": False,
        },
    )

    assert result.option_id == skip_option_id
    assert result.payload == {"skipped": True}


def test_result_for_record_reuses_resolved_payload_from_candidate_metadata() -> None:
    request = DecisionRequest.create(
        "DECLARE_SHOTS",
        "Declare shots",
        player_id="player-1",
        options=[
            DecisionOption.create("Confirm", payload={"action": "confirm", "unit_id": "unit-1"}),
        ],
    )
    option_id = request.options[0].option_id
    action_id = request.action_id_for_option_id(option_id)
    resolved_payload = {
        "declarations": [
            {
                "attacker_unit_id": "unit-1",
                "target_unit_id": "target-1",
                "weapon_key": "bolt rifle",
                "attacks": 3,
            }
        ]
    }
    record = {
        "chosen_action_id": action_id,
        "human_action_injected": False,
        "candidates": [
            {
                "action_id": action_id,
                "params": {"action": "confirm", "unit_id": "unit-1"},
                "metadata": {"resolved_result_payload": resolved_payload},
            }
        ],
    }

    result = ReplayStoreReader._result_for_record(request, record)

    assert result.option_id == option_id
    assert result.payload["declarations"] == resolved_payload["declarations"]


def test_advance_until_request_pending_does_not_consume_future_events() -> None:
    reader = ReplayStoreReader.__new__(ReplayStoreReader)
    game, player = _build_game()
    future_request = DecisionRequest.create(
        "FUTURE_DECISION",
        "Future choice",
        player_id=player.id,
        options=[DecisionOption.create("Confirm", payload={"choice": True})],
    )
    future_event = {
        "event_id": 12,
        "type": "decision_requested",
        "actor_id": player.id,
        "payload": future_request.to_dict(),
    }

    request, cursor = reader._advance_until_request_pending(
        game,
        [future_event],
        0,
        "earlier-decision",
        {},
        stop_event_id=11,
    )

    assert request is None
    assert cursor == 0
    assert game.decision_queue.list() == []


def test_replay_reconstruction_suppresses_charge_phase_followup_queueing() -> None:
    game, player = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE
    game._replay_reconstruction_suppress_charge_followups = True
    queued = []

    def _queue_charge_phase_move_request(**kwargs):
        queued.append(dict(kwargs))
        return None

    game._queue_charge_phase_move_request = _queue_charge_phase_move_request
    request = DecisionRequest.create(
        DECISION_REQUEST_DICE_ROLL,
        "Charge roll",
        player_id=player.id,
        options=[DecisionOption.create("Make Roll", payload={"action_id": "roll"})],
        context={
            "roll_type": "charge",
            "roll_spec": {
                "roll_type": "charge",
                "unit_id": "unit-1",
                "target_unit_ids": ["target-1"],
            },
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=player.id,
        option_id=request.options[0].option_id,
        payload={},
    )

    game._maybe_queue_charge_phase_followup(request, result)

    assert queued == []


def test_prime_request_state_materializes_rerolled_roll_without_queueing_duplicate_request() -> None:
    game, player = _build_game()
    reroll_request = DecisionRequest.create(
        DECISION_SELECT_DICE_REROLL,
        "Re-roll options: Advance roll",
        player_id=player.id,
        options=[
            DecisionOption.create("No re-roll", payload={"action_id": "none"}),
            DecisionOption.create("Re-roll Advance roll", payload={"action_id": "reroll_advance"}),
        ],
        context={
            "roll_id": 7,
            "roll_spec": {
                "dice_count": 1,
                "faces": 6,
                "fixed_dice": [2],
                "reason": "Advance roll",
                "roll_type": "advance",
                "unit_id": "unit-1",
                "reroll_rules": [
                    {
                        "action_id": "reroll_advance",
                        "label": "Re-roll Advance roll",
                        "mode": "all",
                        "source": "rule",
                    }
                ],
            },
        },
    )
    roll_id = int((reroll_request.context or {}).get("roll_id", 0) or 0)

    replay_game, _replay_player = _build_game()
    ReplayStoreReader._prime_request_state(replay_game, reroll_request)

    replay_state = replay_game.roll_manager.get_roll(roll_id)
    assert replay_state is not None
    assert str(replay_state.status) == "rolled"
    assert list(getattr(replay_state, "reroll_options", []) or [])
    assert list(replay_game.decision_queue.list() or []) == []
