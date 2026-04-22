from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_headless_self_play.py"
    spec = importlib.util.spec_from_file_location("run_headless_self_play_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_headless_self_play.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase_state_summary_reports_pre_deployment_setup_phase() -> None:
    mod = _load_script_module()
    game = SimpleNamespace(
        is_in_setup_phase=lambda: True,
        get_current_setup_phase=lambda: SimpleNamespace(name="DEPLOY_ARMIES"),
    )

    assert mod._phase_state_summary(game) == "pre-deployment setup_phase=DEPLOY_ARMIES"


def test_phase_state_summary_reports_post_deployment_phase_with_player_round_and_step() -> None:
    mod = _load_script_module()
    player1 = SimpleNamespace(id="p1", name="Player 1")
    player2 = SimpleNamespace(id="p2", name="Player 2")
    request = SimpleNamespace(
        context={
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
        }
    )
    queue = SimpleNamespace(list=lambda: [request])
    game = SimpleNamespace(
        is_in_setup_phase=lambda: False,
        get_current_player=lambda: player1,
        players=[player1, player2],
        turn=2,
        phase=SimpleNamespace(name="MOVEMENT_PHASE"),
        decision_queue=queue,
        reinforcements_step_active=False,
    )

    assert (
        mod._phase_state_summary(game)
        == "post-deployment player=1 battle_round=2 phase=MOVEMENT_PHASE step=MOVE_UNITS"
    )


def test_game_id_for_index_uses_seed_base_when_present() -> None:
    mod = _load_script_module()

    assert mod._game_id_for_index(3, seed_base=200) == "selfplay:203"
    assert mod._game_id_for_index(3, seed_base=None) == "selfplay:000003"


def test_parse_args_supports_profile_options(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_headless_self_play.py",
            "--profile",
            "--profile-dir",
            str(tmp_path),
            "--profile-sort",
            "cumtime",
            "--profile-lines",
            "25",
            "--profile-label",
            "baseline",
        ],
    )

    args = mod._parse_args()

    assert args.profile is True
    assert args.profile_dir == str(tmp_path)
    assert args.profile_sort == "cumtime"
    assert args.profile_lines == 25
    assert args.profile_label == "baseline"


def test_army_label_from_path_uses_file_stem() -> None:
    mod = _load_script_module()

    assert mod._army_label_from_path("army_lists/chaos_test_2.txt") == "chaos_test_2"


def test_army_labels_from_paths_disambiguates_duplicate_file_stems() -> None:
    mod = _load_script_module()

    labels = mod._army_labels_from_paths(
        "data/profiled_matchups/example/world_eaters/candidate_01_army_list.txt",
        "data/profiled_matchups/example/aeldari/candidate_01_army_list.txt",
    )

    assert labels == ("world_eaters:candidate_01_army_list", "aeldari:candidate_01_army_list")


def test_resolved_replay_base_dir_returns_absolute_path(tmp_path) -> None:
    mod = _load_script_module()

    replay_dir = mod._resolved_replay_base_dir(str(tmp_path / "replays"))

    assert replay_dir == (tmp_path / "replays").resolve()


def test_allocate_replay_session_id_suffixes_conflicts(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()
    attempted_session_ids: list[str] = []

    def _fake_create_session(game, *, base_dir, session_id, label):
        attempted_session_ids.append(str(session_id))
        if len(attempted_session_ids) == 1:
            raise FileExistsError(f"Session already exists: {session_id}")
        return str(session_id)

    monkeypatch.setattr(mod, "create_session", _fake_create_session)

    session_id = mod._allocate_replay_session_id(
        SimpleNamespace(session_id=""),
        replay_base_dir=tmp_path,
        preferred_session_id="selfplay:000000",
        label="chaos_vs_aeldari",
    )

    assert attempted_session_ids == ["selfplay:000000", "selfplay:000000:run001"]
    assert session_id == "selfplay:000000:run001"


def test_export_decision_records_normalizes_uncopyable_objects() -> None:
    mod = _load_script_module()

    class _Uncopyable:
        def __deepcopy__(self, _memo):
            raise AssertionError("deepcopy should not be used for export")

        def __str__(self) -> str:
            return "uncopyable-value"

    exported = mod._export_decision_records(
        [
            {
                "decision_type": "MOVE_UNIT",
                "outcome": {
                    "immediate_deltas": {
                        "value": _Uncopyable(),
                    }
                },
            }
        ]
    )

    assert exported == [
        {
            "decision_type": "MOVE_UNIT",
            "outcome": {
                "immediate_deltas": {
                    "value": "uncopyable-value",
                }
            },
        }
    ]


def test_export_decision_records_deduplicates_decision_ids_and_merges_richer_outcome() -> None:
    mod = _load_script_module()

    exported = mod._export_decision_records(
        [
            {
                "decision_id": "decision:one",
                "decision_type": "CHOOSE_BLESSINGS",
                "wall_clock_ms": 1,
                "outcome": {"immediate_deltas": {"errors": []}, "end_of_turn_return": 0.0},
            },
            {
                "decision_id": "decision:one",
                "decision_type": "CHOOSE_BLESSINGS",
                "wall_clock_ms": 12,
                "outcome": {
                    "immediate_deltas": {"errors": ["late-resolution"], "value": {"ok": True}},
                    "end_of_turn_return": 0.0,
                },
            },
        ]
    )

    assert len(exported) == 1
    assert exported[0]["decision_id"] == "decision:one"
    assert exported[0]["wall_clock_ms"] == 12
    immediate = exported[0]["outcome"]["immediate_deltas"]
    assert immediate["errors"] == ["late-resolution"]
    assert immediate["value"] == {"ok": True}


def test_winner_summary_uses_army_labels_and_winner_first_score_order() -> None:
    mod = _load_script_module()
    player1 = SimpleNamespace(id="p1", get_score=lambda: 17)
    player2 = SimpleNamespace(id="p2", get_score=lambda: 34)

    winner_label, score_line, scoreboard = mod._winner_summary(
        winner=player2,
        player1=player1,
        player2=player2,
        player1_label="chaos_test_2",
        player2_label="aeldari_test_2",
    )

    assert winner_label == "aeldari_test_2"
    assert score_line == "<SCORE: 34 vs 17>"
    assert scoreboard == {"chaos_test_2": 17, "aeldari_test_2": 34}


def test_log_phase_state_if_changed_emits_parenthesized_game_id(caplog) -> None:
    mod = _load_script_module()
    game = SimpleNamespace(
        is_in_setup_phase=lambda: True,
        get_current_setup_phase=lambda: SimpleNamespace(name="DEPLOY_ARMIES"),
    )

    with caplog.at_level(logging.INFO, logger=mod.logger.name):
        state = mod._log_phase_state_if_changed(
            game,
            game_id="selfplay:000001",
            enabled=True,
            last_state=None,
        )

    assert state == "pre-deployment setup_phase=DEPLOY_ARMIES"
    assert "(selfplay:000001 pre-deployment setup_phase=DEPLOY_ARMIES)" in caplog.text


def test_run_single_game_job_serializes_replay_artifact_fields(monkeypatch) -> None:
    mod = _load_script_module()
    captured_kwargs: dict[str, object] = {}

    def _fake_run_single_game(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "game_id": "selfplay:000000",
            "records": [{"decision_type": "choose"}],
            "phase_steps": 12,
            "winner_player_id": "player-1",
            "winner_army_label": "chaos_test",
            "winner_score_line": "<SCORE: 45 vs 32>",
            "scoreboard": {"chaos_test": 45, "aeldari_test": 32},
            "replay_session_id": "selfplay:000000",
            "replay_path": "/tmp/replays/selfplay:000000/replay.sqlite3",
            "snapshot_path": "/tmp/replays/selfplay:000000/snapshot.json",
        }

    monkeypatch.setattr(mod, "_run_single_game", _fake_run_single_game)

    payload = mod._run_single_game_job(
        0,
        player1_army_file="army_lists/chaos_test.txt",
        player2_army_file="army_lists/aeldari_test.txt",
        max_phase_steps=80,
        reserve_policy="forced_only",
        max_reserves_arrival_seconds=10.0,
        deployment_ranker_model="",
        log_level="WARNING",
        log_phase_transitions=False,
        replay_dir="data/headless_self_play_replays",
        replay_keyframe_interval=7,
    )

    assert captured_kwargs["replay_dir"] == "data/headless_self_play_replays"
    assert captured_kwargs["replay_keyframe_interval"] == 7
    result = dict(payload.get("result", {}) or {})
    assert result["replay_session_id"] == "selfplay:000000"
    assert result["replay_path"] == "/tmp/replays/selfplay:000000/replay.sqlite3"
    assert result["snapshot_path"] == "/tmp/replays/selfplay:000000/snapshot.json"


def test_run_single_game_job_writes_profile_artifacts(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()

    def _fake_run_single_game(**_kwargs):
        from warhammer40k_ai.utility.profiling_sections import profile_section

        with profile_section("test.fake_headless_job"):
            total = 0
            for value in range(2000):
                total += value
        return {
            "game_id": "selfplay:000000",
            "records": [{"decision_type": "MOVE_UNIT", "total": total}],
            "phase_steps": 1,
            "winner_player_id": "player-1",
            "winner_army_label": "chaos_test",
            "winner_score_line": "<SCORE: 1 vs 0>",
            "scoreboard": {"chaos_test": 1, "aeldari_test": 0},
        }

    monkeypatch.setattr(mod, "_run_single_game", _fake_run_single_game)

    payload = mod._run_single_game_job(
        0,
        player1_army_file="army_lists/chaos_test.txt",
        player2_army_file="army_lists/aeldari_test.txt",
        max_phase_steps=1,
        profile=True,
        profile_dir=str(tmp_path),
        profile_label="unit_profile",
    )

    artifacts = dict(dict(payload.get("result", {}) or {}).get("profile_artifacts", {}) or {})
    profile_text = Path(str(artifacts.get("profile_text", "")))
    profile_binary = Path(str(artifacts.get("profile_binary", "")))

    assert profile_text.exists()
    assert profile_binary.exists()
    assert "selfplay_000000" in profile_text.name
    text = profile_text.read_text(encoding="utf-8")
    assert "script: scripts/run_headless_self_play.py" in text
    assert "game_id: selfplay:000000" in text
    assert "test.fake_headless_job" in text


def test_run_single_game_preserves_stable_game_id_when_replay_session_suffixes(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()
    created_games: list[object] = []

    class _FakePlayer:
        _next_id = 0

        def __init__(self, name, control=None):
            type(self)._next_id += 1
            self.id = f"player-{type(self)._next_id}"
            self.name = name
            self.control = control
            self.army = None

        def get_score(self):
            return 0

    class _FakeGame:
        def __init__(self, _battlefield, *, players):
            self.players = list(players)
            self.session_id = ""
            self.random_source = SimpleNamespace(seed=lambda _seed: None)
            self.decision_record_store = SimpleNamespace(records=[{"decision_type": "MOVE_UNIT"}])
            created_games.append(self)

        def get_winner(self):
            return self.players[0]

    class _FakeRuntime:
        def __init__(self, _game, **_kwargs):
            self.game_proxy = self

        def is_in_setup_phase(self):
            return False

        def is_game_over(self):
            return True

    def _fake_allocate_replay_session_id(game, *, replay_base_dir, preferred_session_id, label):
        assert replay_base_dir == tmp_path.resolve()
        assert preferred_session_id == "selfplay:000000"
        assert label == "chaos_test_vs_aeldari_test"
        game.session_id = "selfplay:000000:run001"
        return "selfplay:000000:run001"

    def _fake_enable_session_replay_recording(game, *, base_dir, session_id, label, keyframe_interval):
        assert base_dir == tmp_path.resolve()
        assert session_id == "selfplay:000000:run001"
        assert game.session_id == "selfplay:000000:run001"
        assert label == "chaos_test_vs_aeldari_test"
        assert keyframe_interval == 3
        return tmp_path / "selfplay~3A000000~3Arun001" / "replay.sqlite3"

    def _fake_save_session_snapshot(game, *, base_dir, session_id, label):
        assert base_dir == tmp_path.resolve()
        assert session_id == "selfplay:000000:run001"
        assert game.session_id == "selfplay:000000"
        assert label == "chaos_test_vs_aeldari_test"
        game.session_id = session_id
        return tmp_path / "selfplay~3A000000~3Arun001" / "snapshot.json"

    monkeypatch.setattr(mod, "Player", _FakePlayer)
    monkeypatch.setattr(mod, "Game", _FakeGame)
    monkeypatch.setattr(mod, "Battlefield", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(mod, "BattlefieldSize", SimpleNamespace(STRIKE_FORCE="strike-force"))
    monkeypatch.setattr(mod, "HeadlessPolicyDecisionController", lambda **_kwargs: None)
    monkeypatch.setattr(mod, "LocalAuthoritativeRuntime", _FakeRuntime)
    monkeypatch.setattr(mod, "DeterministicDeploymentDecisionMaker", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(mod, "_log_phase_state_if_changed", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mod, "_drain_pending_decisions", lambda *args, **kwargs: kwargs.get("last_state"))
    monkeypatch.setattr(mod, "_allocate_replay_session_id", _fake_allocate_replay_session_id)
    monkeypatch.setattr(mod, "enable_session_replay_recording", _fake_enable_session_replay_recording)
    monkeypatch.setattr(mod, "save_session_snapshot", _fake_save_session_snapshot)

    result = mod._run_single_game(
        game_id="selfplay:000000",
        player1_army_file="army_lists/chaos_test.txt",
        player2_army_file="army_lists/aeldari_test.txt",
        max_phase_steps=1,
        reserve_policy="forced_only",
        max_reserves_arrival_seconds=10.0,
        replay_dir=str(tmp_path),
        replay_keyframe_interval=3,
    )

    assert result["game_id"] == "selfplay:000000"
    assert result["replay_session_id"] == "selfplay:000000:run001"
    assert result["replay_path"] == str(tmp_path / "selfplay~3A000000~3Arun001" / "replay.sqlite3")
    assert result["snapshot_path"] == str(tmp_path / "selfplay~3A000000~3Arun001" / "snapshot.json")
    assert created_games[0].session_id == "selfplay:000000"


def test_run_headless_self_play_writes_machine_readable_report(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()

    def _fake_run_single_game_job(*_args, **_kwargs):
        return {
            "game_index": 0,
            "elapsed_seconds": 0.25,
            "result": {
                "game_id": "selfplay:000000",
                "records": [{"decision_type": "MOVE_UNIT"}],
                "phase_steps": 12,
                "winner_player_id": "player-1",
                "winner_army_label": "chaos_test",
                "winner_score_line": "<SCORE: 45 vs 32>",
                "scoreboard": {"chaos_test": 45, "aeldari_test": 32},
                "replay_session_id": "selfplay:000000",
                "replay_path": "/tmp/replays/selfplay:000000/replay.sqlite3",
                "snapshot_path": "/tmp/replays/selfplay:000000/snapshot.json",
            },
        }

    monkeypatch.setattr(mod, "_run_single_game_job", _fake_run_single_game_job)
    output_path = tmp_path / "records.json"
    report_path = tmp_path / "report.json"

    report = mod.run_headless_self_play(
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        games=1,
        workers=1,
        max_phase_steps=80,
        output=str(output_path),
        no_reward_annotation=True,
        report_output=str(report_path),
    )

    assert report["games_requested"] == 1
    assert report["games_completed"] == 1
    assert report["completion_rate"] == 1.0
    assert report["decision_record_count"] == 1
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["records_output_path"] == str(output_path.resolve())
    assert "records" not in persisted["games"][0]["result"]
    assert persisted["games"][0]["result"]["winner_army_label"] == "chaos_test"


def test_run_headless_self_play_report_includes_profile_artifact_paths(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()

    def _fake_run_single_game_job(*_args, **_kwargs):
        return {
            "game_index": 0,
            "elapsed_seconds": 0.1,
            "result": {
                "game_id": "selfplay:000000",
                "records": [{"decision_type": "MOVE_UNIT"}],
                "phase_steps": 1,
                "winner_player_id": "player-1",
                "winner_army_label": "chaos_test",
                "winner_score_line": "<SCORE: 1 vs 0>",
                "scoreboard": {"chaos_test": 1, "aeldari_test": 0},
                "profile_artifacts": {
                    "profile_text": "/tmp/profile.txt",
                    "profile_binary": "/tmp/profile.prof",
                },
            },
        }

    monkeypatch.setattr(mod, "_run_single_game_job", _fake_run_single_game_job)
    output_path = tmp_path / "records.json"
    report_path = tmp_path / "report.json"

    report = mod.run_headless_self_play(
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        games=1,
        workers=1,
        max_phase_steps=1,
        output=str(output_path),
        no_reward_annotation=True,
        report_output=str(report_path),
        profile=True,
    )

    assert report["profile_artifacts"] == [
        {
            "game_index": 0,
            "game_id": "selfplay:000000",
            "profile_text": "/tmp/profile.txt",
            "profile_binary": "/tmp/profile.prof",
        }
    ]
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    assert persisted["profile_artifacts"][0]["profile_text"] == "/tmp/profile.txt"
