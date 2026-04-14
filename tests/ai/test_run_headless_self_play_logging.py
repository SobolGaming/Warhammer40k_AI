from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
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


def test_army_label_from_path_uses_file_stem() -> None:
    mod = _load_script_module()

    assert mod._army_label_from_path("army_lists/chaos_test_2.txt") == "chaos_test_2"


def test_resolved_replay_base_dir_returns_absolute_path(tmp_path) -> None:
    mod = _load_script_module()

    replay_dir = mod._resolved_replay_base_dir(str(tmp_path / "replays"))

    assert replay_dir == (tmp_path / "replays").resolve()


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
