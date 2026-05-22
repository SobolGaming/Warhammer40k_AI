from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

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


def test_checked_in_example_weight_sets_load() -> None:
    mod = _load_script_module()
    config_path = Path(__file__).resolve().parents[2] / "data" / "ranker_weight_sweeps" / "example_weight_sets.json"

    weight_sets = mod._load_weight_sets(str(config_path), baseline_weight_set_id="baseline")

    assert [item["weight_set_id"] for item in weight_sets] == [
        "baseline",
        "score_pressure",
        "commander_alignment_pressure",
    ]
    score_focus = weight_sets[1]
    orchestrator = mod.build_orchestrator_for_weight_set(score_focus)
    assert orchestrator.component_implementations()["movement_ranker"].component_name == "movement_ranker"


def test_weight_set_fingerprint_ignores_non_behavioral_identity_fields() -> None:
    mod = _load_script_module()
    first = {
        "weight_set_id": "score_pressure",
        "description": "Original label.",
        "component_weight_multipliers": {
            "movement_ranker": {"projected_score_delta_next_window": 1.15}
        },
    }
    second = {
        "weight_set_id": "renamed_attempt",
        "description": "Different label.",
        "notes": "Different human notes.",
        "component_weight_multipliers": {
            "movement_ranker": {"projected_score_delta_next_window": 1.15}
        },
    }
    changed = {
        "weight_set_id": "changed_attempt",
        "description": "Behavioral change.",
        "component_weight_multipliers": {
            "movement_ranker": {"projected_score_delta_next_window": 1.2}
        },
    }

    assert mod.weight_set_fingerprint(first) == mod.weight_set_fingerprint(second)
    assert mod.weight_set_fingerprint(first) != mod.weight_set_fingerprint(changed)


def test_rejection_registry_skips_matching_functional_weight_sets() -> None:
    mod = _load_script_module()
    rejected = {
        "weight_set_id": "score_pressure",
        "component_weight_multipliers": {
            "movement_ranker": {"projected_score_delta_next_window": 1.15}
        },
    }
    renamed_rejected = {
        "weight_set_id": "same_knobs_new_name",
        "description": "Same behavior should still be skipped.",
        "component_weight_multipliers": {
            "movement_ranker": {"projected_score_delta_next_window": 1.15}
        },
    }
    fresh = {
        "weight_set_id": "fresh_action",
        "component_weight_multipliers": {
            "movement_ranker": {"projected_score_delta_next_window": 1.05}
        },
    }
    registry = {
        "schema_version": 1,
        "rejected_weight_sets": [
            {
                "weight_set_id": "score_pressure",
                "status": "reject",
                "candidate_fingerprint": mod.weight_set_fingerprint(rejected),
                "blockers": ["win_count_delta_below_threshold"],
            }
        ],
    }

    selected, skipped = mod._filter_rejected_weight_sets(
        [
            {"weight_set_id": "baseline", "components": {}},
            renamed_rejected,
            fresh,
        ],
        baseline_weight_set_id="baseline",
        registry=registry,
        allow_rejected=False,
    )

    assert [item["weight_set_id"] for item in selected] == ["baseline", "fresh_action"]
    assert skipped == [
        {
            "weight_set_id": "same_knobs_new_name",
            "candidate_fingerprint": mod.weight_set_fingerprint(rejected),
            "matched_rejected_weight_set_id": "score_pressure",
            "blockers": ["win_count_delta_below_threshold"],
            "source_analysis_path": "",
        }
    ]


def test_hash_seed_guard_reexecs_cli_with_deterministic_seed(monkeypatch) -> None:
    mod = _load_script_module()
    calls = []

    def fake_execvpe(executable, argv, env):
        calls.append((executable, list(argv), dict(env)))
        raise RuntimeError("reexec")

    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    monkeypatch.delenv("WH40K_ALLOW_RANDOM_HASH_SEED", raising=False)
    monkeypatch.setattr(mod.os, "execvpe", fake_execvpe)
    monkeypatch.setattr(mod.sys, "argv", ["run_ranker_weight_sweep.py", "--example"])

    with pytest.raises(RuntimeError, match="reexec"):
        mod._ensure_deterministic_python_hash_seed()

    assert calls
    assert calls[0][2]["PYTHONHASHSEED"] == "0"
    assert calls[0][1] == [mod.sys.executable, "run_ranker_weight_sweep.py", "--example"]


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
