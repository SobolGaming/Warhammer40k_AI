import json

from warhammer40k_ai.engine.battlefield import Battlefield
from warhammer40k_ai.engine.command_kinds import CMD_SET_DEPLOYMENT_WAITING
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.session_store import (
    MANIFEST_FILENAME,
    SNAPSHOT_FILENAME,
    create_session,
    delete_session,
    enable_phase_end_autosave,
    list_sessions,
    load_session_snapshot,
    save_session_snapshot,
)
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl


def _build_game() -> Game:
    army_one = Army("Necrons", "Awakened Dynasty")
    army_two = Army("Orks", "Waaagh!")
    player_one = Player("P1", control=PlayerControl.LOCAL, army=army_one)
    player_two = Player("P2", control=PlayerControl.REMOTE, army=army_two)
    game = Game(Battlefield(width=60, height=44), players=[player_one, player_two])
    game.turn = 1
    return game


def test_session_store_roundtrip(tmp_path):
    game = _build_game()
    session_id = create_session(game, base_dir=tmp_path, label="Test Session")

    manifest_path = tmp_path / session_id / MANIFEST_FILENAME
    snapshot_path = tmp_path / session_id / SNAPSHOT_FILENAME
    assert manifest_path.exists()
    assert not snapshot_path.exists()

    saved_path = save_session_snapshot(game, base_dir=tmp_path, session_id=session_id)
    assert saved_path == snapshot_path
    assert snapshot_path.exists()

    manifest = json.loads(manifest_path.read_text())
    assert manifest["session_id"] == session_id
    assert manifest["battle_round"] == 1
    assert manifest["players"][0]["faction"] in ("Necrons", "Orks")
    assert manifest["players"][0]["detachment_type"]
    assert manifest["players"][0]["control"] in ("LOCAL", "REMOTE")
    assert manifest["players"][0]["agent_type"] == "human"

    loaded = load_session_snapshot(session_id, base_dir=tmp_path)
    assert isinstance(loaded, Game)
    assert getattr(loaded, "session_id", None) == session_id

    sessions = list_sessions(base_dir=tmp_path)
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == session_id

    delete_session(session_id, base_dir=tmp_path)
    assert not (tmp_path / session_id).exists()
    assert list_sessions(base_dir=tmp_path) == []


def test_phase_end_autosave_flushes_events(tmp_path):
    game = _build_game()
    session_id = enable_phase_end_autosave(game, base_dir=tmp_path, label="Autosave")

    command = GameCommand.create(CMD_SET_DEPLOYMENT_WAITING, payload={"value": True})
    game.apply_command(command)
    assert game.event_log.events

    game.event_system.publish("phase_end", player=game.get_current_player(), phase=game.phase)

    snapshot_path = tmp_path / session_id / SNAPSHOT_FILENAME
    assert snapshot_path.exists()
    assert game.event_log.events == []
