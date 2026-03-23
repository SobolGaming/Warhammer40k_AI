from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_headless_self_play.py"
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
