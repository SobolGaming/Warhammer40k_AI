import json

import pytest

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.command_kinds import CMD_SET_DEPLOYMENT_WAITING
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.replay_store import disable_decision_replay_recording
from warhammer40k_ai.engine.session_store import (
    MANIFEST_FILENAME,
    REPLAY_FILENAME,
    SNAPSHOT_FILENAME,
    create_session,
    delete_session,
    enable_phase_end_autosave,
    enable_session_replay_recording,
    list_sessions,
    load_session_replay_reader,
    load_session_snapshot,
    resolve_session_path,
    resolve_session_replay_path,
    save_session_snapshot,
)
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _build_game() -> Game:
    army_one = Army.with_detachment("Necrons", "Awakened Dynasty")
    army_two = Army.with_detachment("Orks", "Waaagh!")
    player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.turn = 1
    return game


def test_session_store_roundtrip(tmp_path):
    game = _build_game()
    session_id = create_session(game, base_dir=tmp_path, label="Test Session")
    session_path = resolve_session_path(session_id, base_dir=tmp_path)

    manifest_path = session_path / MANIFEST_FILENAME
    snapshot_path = session_path / SNAPSHOT_FILENAME
    assert manifest_path.exists()
    assert not snapshot_path.exists()

    saved_path = save_session_snapshot(game, base_dir=tmp_path, session_id=session_id)
    assert saved_path == snapshot_path
    assert snapshot_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["session_id"] == session_id
    assert manifest["battle_round"] == 1
    assert manifest["players"][0]["faction"] in ("Necrons", "Orks")
    assert manifest["players"][0]["primary_detachment_type"]
    assert "detachment_type" not in manifest["players"][0]
    assert manifest["players"][0]["control"] in ("LOCAL", "REMOTE")
    assert manifest["players"][0]["agent_type"] == "human"

    loaded = load_session_snapshot(session_id, base_dir=tmp_path)
    assert isinstance(loaded, Game)
    assert getattr(loaded, "session_id", None) == session_id

    sessions = list_sessions(base_dir=tmp_path)
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == session_id

    delete_session(session_id, base_dir=tmp_path)
    assert not session_path.exists()
    assert list_sessions(base_dir=tmp_path) == []


def test_phase_end_autosave_flushes_events(tmp_path):
    game = _build_game()
    session_id = enable_phase_end_autosave(game, base_dir=tmp_path, label="Autosave")

    command = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={"value": True})
    game.apply_command(command)
    assert game.event_log.events

    game.event_system.publish("phase_end", player=game.get_current_player(), phase=game.phase)

    snapshot_path = resolve_session_path(session_id, base_dir=tmp_path) / SNAPSHOT_FILENAME
    assert snapshot_path.exists()
    assert game.event_log.events == []


def test_session_replay_recording_persists_decision_timeline(tmp_path):
    game = _build_game()
    session_id = create_session(game, base_dir=tmp_path, label="Replay Session")
    session_path = resolve_session_path(session_id, base_dir=tmp_path)
    replay_path = enable_session_replay_recording(
        game,
        base_dir=tmp_path,
        session_id=session_id,
        label="Replay Session",
        keyframe_interval=1,
    )
    assert replay_path == session_path / REPLAY_FILENAME
    assert replay_path.exists()

    player = game.players[0]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm replay capture",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    apply_result = game.resolve_decision(
        DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=request.options[0].option_id,
            payload={},
        )
    )
    assert bool(getattr(apply_result, "ok", False))

    reader = load_session_replay_reader(session_id, base_dir=tmp_path)
    assert reader.decision_count() == 1
    steps = reader.list_steps(limit=10)
    assert len(steps) == 1
    assert steps[0].decision_type == DECISION_CONFIRM_YES_NO


def test_session_snapshot_flushes_post_decision_replay_tail_into_latest_keyframe(tmp_path):
    game = _build_game()
    session_id = create_session(game, base_dir=tmp_path, label="Replay Tail Session")
    enable_session_replay_recording(
        game,
        base_dir=tmp_path,
        session_id=session_id,
        label="Replay Tail Session",
        keyframe_interval=25,
    )

    player = game.players[0]
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm replay tail capture",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
    )
    game.request_decision(request)
    apply_result = game.resolve_decision(
        DecisionResult(
            decision_id=request.decision_id,
            player_id=player.id,
            option_id=request.options[0].option_id,
            payload={},
        )
    )
    assert bool(getattr(apply_result, "ok", False))

    save_session_snapshot(game, base_dir=tmp_path, session_id=session_id, label="Replay Tail Session")
    game.award_vp(
        player,
        5,
        source="battle_ready",
        timing="End of battle",
        details="Replay tail regression",
    )
    save_session_snapshot(game, base_dir=tmp_path, session_id=session_id, label="Replay Tail Session")

    reader = load_session_replay_reader(session_id, base_dir=tmp_path)
    replayed = reader.reconstruct_game_at_decision(reader.decision_count(), strict=True)

    assert reader.decision_count() == 1
    assert reader.keyframe_count() >= 3
    assert replayed.players[0].vp_battle_ready == 5
    assert replayed.players[0].get_score() == game.players[0].get_score()


def test_session_store_encodes_filesystem_unsafe_session_ids(tmp_path):
    game = _build_game()
    session_id = "selfplay:000000"
    session_path = resolve_session_path(session_id, base_dir=tmp_path)
    replay_path = resolve_session_replay_path(session_id, base_dir=tmp_path)

    assert session_path == tmp_path / "selfplay~3A000000"
    assert replay_path == session_path / REPLAY_FILENAME

    created_session_id = create_session(game, base_dir=tmp_path, session_id=session_id, label="Encoded Session")
    snapshot_path = save_session_snapshot(game, base_dir=tmp_path, session_id=session_id, label="Encoded Session")
    recorded_replay_path = enable_session_replay_recording(
        game,
        base_dir=tmp_path,
        session_id=session_id,
        label="Encoded Session",
        keyframe_interval=1,
    )

    assert created_session_id == session_id
    assert session_path.exists()
    assert snapshot_path == session_path / SNAPSHOT_FILENAME
    assert recorded_replay_path == replay_path

    manifest = json.loads((session_path / MANIFEST_FILENAME).read_text())
    assert manifest["session_id"] == session_id

    loaded = load_session_snapshot(session_id, base_dir=tmp_path)
    assert isinstance(loaded, Game)
    reader = load_session_replay_reader(session_id, base_dir=tmp_path)
    assert reader.decision_count() == 0

    disable_decision_replay_recording(game)
    delete_session(session_id, base_dir=tmp_path)
    assert not session_path.exists()
