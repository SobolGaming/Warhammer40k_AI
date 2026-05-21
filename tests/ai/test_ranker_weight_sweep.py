from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionRequest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "run_ranker_weight_sweep.py"
    spec = importlib.util.spec_from_file_location("run_ranker_weight_sweep_module", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_ranker_weight_sweep.py for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _records(game_id: str = "general_profile_eval:000000:seed:101") -> list[dict]:
    return [
        {
            "game_id": game_id,
            "global_seed": 101,
            "turn_id": 1,
            "phase": "MOVEMENT_PHASE",
            "decision_id": f"{game_id}:decision-1",
            "decision_type": "MOVE_UNIT",
            "request_context": {
                "player_id": "player-1",
                "deployment_dirty_flags": {"status": "dirty"},
                "deployment_candidate_tempo_capabilities": {
                    "unit-1": {"has_scout": True, "has_infiltrate": False}
                },
            },
            "candidates": [
                {
                    "action_id": "candidate-a",
                    "params": {"unit_id": "unit-1"},
                    "metadata": {
                        "fallback_mode": True,
                        "projected_score_delta_next_window": 1.0,
                    },
                },
                {
                    "action_id": "candidate-b",
                    "params": {"unit_id": "unit-1"},
                    "metadata": {
                        "commander_alignment": {"role": "move"},
                        "projected_score_delta_next_window": 2.0,
                    },
                },
            ],
            "mask": [True, True],
            "chosen_action_id": "candidate-b",
        }
    ]


def test_weight_set_orchestrator_applies_component_weight_overrides() -> None:
    mod = _load_script_module()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move",
        player_id="player-1",
        context={"phase_name": "MOVEMENT_PHASE"},
        candidates=[
            CandidateAction("candidate-a", params={}, metadata={"projected_score_delta_next_window": 1.0}),
            CandidateAction("candidate-b", params={}, metadata={"projected_score_delta_next_window": 3.0}),
        ],
        mask=[True, True],
    )

    baseline = mod.build_orchestrator_for_weight_set({"weight_set_id": "baseline"})
    inverted = mod.build_orchestrator_for_weight_set(
        {
            "weight_set_id": "inverted",
            "components": {
                "movement_ranker": {
                    "weights": {"projected_score_delta_next_window": -10.0},
                }
            },
        }
    )

    assert baseline.choose_action(request).action_id == "candidate-b"
    assert inverted.choose_action(request).action_id == "candidate-a"


def test_ranker_weight_sweep_main_writes_report_and_baseline_delta(monkeypatch, tmp_path) -> None:
    mod = _load_script_module()
    profiles_path = tmp_path / "profiles.json"
    weights_path = tmp_path / "weight_sets.json"
    output_dir = tmp_path / "sweep"
    profiles_path.write_text(
        json.dumps(
            {
                "default_player1_army": "army_lists/chaos_test.txt",
                "default_player2_army": "army_lists/aeldari_test.txt",
                "default_seed": 101,
                "profiles": [{"id": "alpha", "index": 1, "description": "Alpha"}],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    weights_path.write_text(
        json.dumps(
            {
                "weight_sets": [
                    {
                        "weight_set_id": "score_focus",
                        "description": "Favor projected score metadata.",
                        "component_weight_multipliers": {
                            "movement_ranker": {"projected_score_delta_next_window": 1.25}
                        },
                    }
                ]
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    def fake_run_profile_game(**kwargs):
        assert kwargs["collect_records"] is True
        assert kwargs["ai_orchestrator"] is not None
        player1_label, player2_label = mod.profile_eval.self_play._army_labels_from_paths(
            str(kwargs["player1_army"]),
            str(kwargs["player2_army"]),
        )
        weight_set_id = Path(kwargs["output_dir"]).name
        if weight_set_id == "score_focus":
            player1_score = 14
            player2_score = 8
        else:
            player1_score = 10
            player2_score = 9
        label = mod.profile_eval._profile_pair_label(kwargs["player1_profile"], kwargs["player2_profile"])
        summary = {
            "profile_pair_id": label,
            "seed": int(kwargs["seed"]),
            "player1_profile_id": "alpha",
            "player2_profile_id": "alpha",
            "player1_profile_index": 1,
            "player2_profile_index": 1,
            "winner_army_label": player1_label,
            "winner_score_line": f"<SCORE: {player1_score} vs {player2_score}>",
            "elapsed_seconds": 0.1,
            "phase_steps": 4,
            "decision_record_count": 1,
            "scoreboard": {player1_label: player1_score, player2_label: player2_score},
            "records_path": "",
            "summary_path": str(Path(kwargs["output_dir"]) / f"{label}_summary.json"),
        }
        return summary, _records(game_id=f"{weight_set_id}:game")

    monkeypatch.setattr(mod.profile_eval, "_run_profile_game", fake_run_profile_game)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_ranker_weight_sweep.py",
            "--profiles",
            str(profiles_path),
            "--weight-sets",
            str(weights_path),
            "--profile-id",
            "alpha",
            "--output-dir",
            str(output_dir),
            "--ui-smoke-status",
            "pass",
            "--network-smoke-status",
            "pass",
            "--snapshot-smoke-status",
            "pass",
        ],
    )

    assert mod.main() == 0
    report = json.loads((output_dir / "weight_sweep_report.json").read_text(encoding="utf-8"))
    rows_by_id = {row["weight_set_id"]: row for row in report["rows"]}

    assert report["weight_set_count"] == 2
    assert set(rows_by_id) == {"baseline", "score_focus"}
    assert rows_by_id["baseline"]["baseline_delta"]["mean_vp_differential_player1_minus_player2"] == 0.0
    assert rows_by_id["score_focus"]["baseline_delta"]["mean_vp_differential_player1_minus_player2"] == 5.0
    assert rows_by_id["score_focus"]["profile_pair_count"] == 1
    assert rows_by_id["score_focus"]["fallback_rate"] == 0.5
    assert (output_dir / "score_focus" / "matrix_report.json").is_file()
    assert (output_dir / "score_focus" / "ranker_training_rows.jsonl").is_file()
    assert (output_dir / "score_focus" / "ranker_training_coverage.json").is_file()
