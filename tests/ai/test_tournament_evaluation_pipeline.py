from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.ml import ArtifactManifestStore
from warhammer40k_ai.ml.evaluation_pipeline import (
    HEADLESS_FIXED_EVALUATION_MODE,
    TRAINING_GRADE_EVALUATION_MODE,
    run_policy_bundle_evaluation,
    run_tournament_roster_evaluation,
)
from warhammer40k_ai.roster.army_build import ArmyBlueprint, DetachmentSelection, RosterEntry
from warhammer40k_ai.roster.event_policy import chapter_approved_10e_event_policy
from warhammer40k_ai.roster.muster_manifest import validate_mustering_manifest
from warhammer40k_ai.roster.muster_record import validate_muster_record
from warhammer40k_ai.roster.tournament_field import OpponentSlice, TournamentFieldDistribution, WeightedChoice


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_script_module(script_name: str):
    script_path = Path(__file__).resolve().parents[2] / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(f"test_{script_name.replace('.', '_')}", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {script_name} for testing.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bundle_payload(bundle_id: str) -> dict[str, object]:
    return {
        "policy_bundle_schema_id": "policy_bundle_schema:v1",
        "policy_bundle_id": bundle_id,
        "controller_type": "headless_self_play",
        "rules_bundle_scope": {
            "match_mode": "exact",
            "ids": ["rules_bundle:test_bundle"],
        },
        "descriptor_bundle_scope": {
            "match_mode": "exact",
            "ids": ["descriptor_bundle:test_bundle"],
        },
        "event_policy_scope": {
            "match_mode": "exact",
            "ids": ["event_policy:chapter_approved_10e_singles_v1"],
        },
        "components": {
            "candidate_ranker": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:headless_candidate_ranker:v1",
            },
            "matchup_evaluator": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:capability_matchup:v1",
            },
            "playbook_selector": {
                "resolver_kind": "heuristic",
                "resolver_ref": "heuristic:identity_playbook:v1",
            },
        },
        "fallbacks": {
            "playbook_selector": ["heuristic:identity_playbook_fallback:v1"]
        },
        "required_feature_schema_ids": ["feature_schema:roster_matchup_v1"],
        "required_capability_schema_ids": ["capability_schema:build_capability_v1"],
        "created_from_commit": "0123456789abcdef0123456789abcdef01234567",
    }


def _rules_bundle() -> RulesetBundle:
    return RulesetBundle.from_values(
        core_rules_id="core_rules:test",
        rules_commentary_id="rules_commentary:test",
        mission_pack_id="mission_pack:test",
        terrain_pack_id="terrain_pack:test",
        dataslate_id="dataslate:test",
        points_id="points:test",
        faction_pack_id="faction_pack:test",
        detachment_pack_id="detachment_pack:test",
    )


def _record(decision_id: str, *, game_id: str, player_score: int, opponent_score: int) -> dict[str, object]:
    rules_bundle = _rules_bundle()
    return {
        "decision_id": decision_id,
        "decision_type": "MOVE_UNIT",
        "game_id": game_id,
        "rules_bundle_id": str(rules_bundle.rules_bundle_id),
        "rules_bundle": rules_bundle.to_dict(),
        "descriptor_bundle_id": "descriptor_bundle:test_bundle",
        "omniscient_state": {
            "players": [
                {"player_id": "player:test:1", "score": player_score},
                {"player_id": "player:test:2", "score": opponent_score},
            ]
        },
        "descriptor_ids": {
            "mission_descriptor_id": "mission_descriptor:test",
            "objective_descriptor_ids": ["objective_descriptor:test"],
            "terrain_descriptor_ids": ["terrain_descriptor:test"],
            "deployment_descriptor_id": "deployment_descriptor:test",
            "army_build_descriptor_id": "army_build_descriptor:test",
            "tool_descriptor_ids": ["tool_descriptor:test"],
        },
        "candidates": [
            {
                "action_id": f"{decision_id}:a",
                "params": {},
                "metadata": {
                    "projected_score_delta_next_window": 0.5,
                    "projected_score_delta_round": 0.25,
                    "projected_deny_delta_next_window": 0.0,
                    "projected_control_delta": 0.1,
                    "projected_action_enablement_delta": 0.2,
                    "projected_exposure_delta": -0.1,
                    "projected_trade_ev": 0.3,
                    "cover_delta": 0.0,
                    "los_delta": 0.0,
                    "resource_delta": 0.0,
                    "rules_provenance_refs": [str(rules_bundle.rules_bundle_id)],
                },
            }
        ],
        "mask": [True],
        "chosen_action_id": f"{decision_id}:a",
        "valid": True,
    }


def _self_play_report(records: list[dict[str, object]]) -> dict[str, object]:
    return {
        "games_requested": 1,
        "games_completed": 1,
        "games_failed": 0,
        "completion_rate": 1.0,
        "decision_record_count": len(records),
        "games": [
            {
                "game_index": 0,
                "elapsed_seconds": 0.25,
                "result": {
                    "game_id": "game:test:0",
                    "phase_steps": 12,
                    "winner_army_label": "chaos_test",
                    "winner_score_line": "<SCORE: 12 vs 8>",
                    "scoreboard": {"chaos_test": 12, "aeldari_test": 8},
                    "replay_session_id": "game:test:0",
                    "replay_path": "/tmp/replay.sqlite3",
                    "snapshot_path": "/tmp/snapshot.json",
                },
            }
        ],
    }


def _fake_self_play_stage(records: list[dict[str, object]]):
    def _run(**_kwargs):
        return {
            "returncode": 0,
            "stdout_path": "",
            "stderr_path": "",
            "records_path": "",
            "report_path": "",
            "report": _self_play_report(records),
            "records": records,
            "replay_dir": "",
        }

    return _run


def _fake_partial_timeout_self_play_stage(records: list[dict[str, object]], *, stderr_path: Path):
    def _run(**_kwargs):
        return {
            "returncode": 1,
            "stdout_path": "",
            "stderr_path": str(stderr_path),
            "records_path": "",
            "report_path": "",
            "report": {
                "games_requested": 4,
                "games_completed": 1,
                "games_failed": 3,
                "completion_rate": 0.25,
                "decision_record_count": len(records),
                "games": [
                    {
                        "game_index": 0,
                        "elapsed_seconds": 0.25,
                        "result": {
                            "game_id": "game:test:0",
                            "phase_steps": 12,
                            "winner_army_label": "chaos_test",
                            "winner_score_line": "<SCORE: 12 vs 8>",
                            "scoreboard": {"chaos_test": 12, "aeldari_test": 8},
                            "replay_session_id": "game:test:0",
                            "replay_path": "/tmp/replay.sqlite3",
                            "snapshot_path": "/tmp/snapshot.json",
                        },
                    }
                ],
            },
            "records": records,
            "replay_dir": "",
        }

    return _run


def _fake_replay_pass(_report):
    return {
        "games_audited": 1,
        "games_passed": 1,
        "replay_pass_rate": 1.0,
        "decision_steps_audited": 2,
        "passed": True,
        "per_game": {
            "game:test:0": {
                "ok": True,
                "decision_count": 2,
                "error": "",
            }
        },
        "failures": [],
    }


def _fake_replay_fail(_report):
    return {
        "games_audited": 1,
        "games_passed": 0,
        "replay_pass_rate": 0.0,
        "decision_steps_audited": 0,
        "passed": False,
        "per_game": {
            "game:test:0": {
                "ok": False,
                "decision_count": 0,
                "error": "ValueError: replay drift",
            }
        },
        "failures": [{"game_id": "game:test:0", "error": "ValueError: replay drift"}],
    }


def test_policy_bundle_smoke_evaluation_is_deterministic_for_fixed_seed(tmp_path: Path, monkeypatch) -> None:
    records = [
        _record("d1", game_id="game:test:0", player_score=0, opponent_score=0),
        _record("d2", game_id="game:test:0", player_score=12, opponent_score=8),
    ]
    models_root = tmp_path / "models"
    bundle_path = ArtifactManifestStore(models_root).bundle_manifest_path("policy_bundle:heuristic_eval_v1")
    _write_json(bundle_path, _bundle_payload("policy_bundle:heuristic_eval_v1"))

    import warhammer40k_ai.ml.evaluation_pipeline as pipeline

    monkeypatch.setattr(pipeline, "run_headless_self_play_stage", _fake_self_play_stage(records))
    monkeypatch.setattr(pipeline, "audit_replay_sessions", _fake_replay_pass)

    first = run_policy_bundle_evaluation(
        policy_bundle_source=str(bundle_path),
        models_root=models_root,
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        report_dir=tmp_path / "report_a",
        games=1,
        seed_base=123,
        evaluation_mode=HEADLESS_FIXED_EVALUATION_MODE,
    )
    second = run_policy_bundle_evaluation(
        policy_bundle_source=str(bundle_path),
        models_root=models_root,
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        report_dir=tmp_path / "report_b",
        games=1,
        seed_base=123,
        evaluation_mode=HEADLESS_FIXED_EVALUATION_MODE,
    )

    assert first["success"] is True
    assert second["success"] is True
    assert first["summary"]["utility_decomposition"] == second["summary"]["utility_decomposition"]
    assert first["summary"]["manifest_gate"]["gate_profile_id"] == "headless_fixed_v1"


def test_policy_bundle_evaluation_fails_when_replay_audit_fails(tmp_path: Path, monkeypatch) -> None:
    records = [_record("d1", game_id="game:test:0", player_score=4, opponent_score=4)]
    models_root = tmp_path / "models"
    bundle_path = ArtifactManifestStore(models_root).bundle_manifest_path("policy_bundle:heuristic_eval_v1")
    _write_json(bundle_path, _bundle_payload("policy_bundle:heuristic_eval_v1"))

    import warhammer40k_ai.ml.evaluation_pipeline as pipeline

    monkeypatch.setattr(pipeline, "run_headless_self_play_stage", _fake_self_play_stage(records))
    monkeypatch.setattr(pipeline, "audit_replay_sessions", _fake_replay_fail)

    result = run_policy_bundle_evaluation(
        policy_bundle_source=str(bundle_path),
        models_root=models_root,
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        report_dir=tmp_path / "report",
        games=1,
        evaluation_mode=HEADLESS_FIXED_EVALUATION_MODE,
    )

    assert result["success"] is False
    assert "replay_audit_failed" in result["summary"]["failure_reasons"]


def test_policy_bundle_training_grade_fails_pre_ml_baseline_gate(tmp_path: Path, monkeypatch) -> None:
    records = [_record("d1", game_id="game:test:0", player_score=4, opponent_score=4)]
    models_root = tmp_path / "models"
    bundle_path = ArtifactManifestStore(models_root).bundle_manifest_path("policy_bundle:heuristic_eval_v1")
    _write_json(bundle_path, _bundle_payload("policy_bundle:heuristic_eval_v1"))

    import warhammer40k_ai.ml.evaluation_pipeline as pipeline

    monkeypatch.setattr(pipeline, "run_headless_self_play_stage", _fake_self_play_stage(records))
    monkeypatch.setattr(pipeline, "audit_replay_sessions", _fake_replay_pass)

    result = run_policy_bundle_evaluation(
        policy_bundle_source=str(bundle_path),
        models_root=models_root,
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        report_dir=tmp_path / "report",
        games=1,
        evaluation_mode=TRAINING_GRADE_EVALUATION_MODE,
    )

    assert result["success"] is False
    assert result["gate_report"]["gate_profile_id"] == "pre_ml_baseline_v1"
    assert any("manifest_gate_failed:pre_ml_baseline_v1" == item for item in result["summary"]["failure_reasons"])


def test_policy_bundle_evaluation_reports_timeout_ratio_across_requested_games(tmp_path: Path, monkeypatch) -> None:
    records = [_record("d1", game_id="game:test:0", player_score=4, opponent_score=4)]
    models_root = tmp_path / "models"
    bundle_path = ArtifactManifestStore(models_root).bundle_manifest_path("policy_bundle:heuristic_eval_v1")
    _write_json(bundle_path, _bundle_payload("policy_bundle:heuristic_eval_v1"))
    stderr_path = tmp_path / "self_play_stderr.txt"
    stderr_path.write_text("Worker timed out after max phase steps on remaining games.", encoding="utf-8")

    import warhammer40k_ai.ml.evaluation_pipeline as pipeline

    monkeypatch.setattr(
        pipeline,
        "run_headless_self_play_stage",
        _fake_partial_timeout_self_play_stage(records, stderr_path=stderr_path),
    )
    monkeypatch.setattr(pipeline, "audit_replay_sessions", _fake_replay_pass)

    result = run_policy_bundle_evaluation(
        policy_bundle_source=str(bundle_path),
        models_root=models_root,
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        report_dir=tmp_path / "report",
        games=4,
        evaluation_mode=HEADLESS_FIXED_EVALUATION_MODE,
    )

    assert result["success"] is False
    assert result["summary"]["utility_decomposition"]["timeout_or_max_phase_step_exit_ratio"] == 0.75
    assert "timeout_exit" in result["summary"]["failure_reasons"]
    assert "max_phase_steps_exit" in result["summary"]["failure_reasons"]


def test_tournament_roster_evaluation_adds_roster_context(tmp_path: Path, monkeypatch) -> None:
    records = [
        _record("d1", game_id="game:test:0", player_score=0, opponent_score=0),
        _record("d2", game_id="game:test:0", player_score=12, opponent_score=8),
    ]
    models_root = tmp_path / "models"
    bundle_path = ArtifactManifestStore(models_root).bundle_manifest_path("policy_bundle:heuristic_eval_v1")
    _write_json(bundle_path, _bundle_payload("policy_bundle:heuristic_eval_v1"))

    blueprint = ArmyBlueprint(
        faction="Space Marines",
        detachments=[
            DetachmentSelection(
                selection_id="det_gladius",
                detachment_type="Gladius Task Force",
            )
        ],
        unit_entries=[
            RosterEntry(
                entry_id="entry_intercessors",
                name="Intercessor Squad",
                count=5,
                detachment_selection_id="det_gladius",
            )
        ],
    )
    event_policy = chapter_approved_10e_event_policy()
    field_distribution = TournamentFieldDistribution(
        rules_bundle_id="rules_bundle:test_bundle",
        event_policy_id=event_policy.event_policy_id,
        terrain_layout_pack_id="terrain_pack:test",
        opponent_slices=(
            OpponentSlice(
                slice_id="slice:test",
                weight=1.0,
                label="Test",
                faction="Aeldari",
            ),
        ),
        mission_distribution=(WeightedChoice(choice_id="mission:test", weight=1.0),),
        deployment_distribution=(WeightedChoice(choice_id="deployment:test", weight=1.0),),
        terrain_distribution=(WeightedChoice(choice_id="terrain:test", weight=1.0),),
    )
    blueprint_path = tmp_path / "blueprint.json"
    event_policy_path = tmp_path / "event_policy.json"
    field_path = tmp_path / "field.json"
    _write_json(blueprint_path, blueprint.to_dict())
    _write_json(event_policy_path, event_policy.to_dict())
    _write_json(field_path, field_distribution.to_dict())

    class _FakeProfile:
        capability_schema_id = "capability_schema:build_capability_v1"
        build_capability_profile_id = "build_capability_profile:test"
        army_blueprint_hash = blueprint.army_blueprint_hash

        def to_dict(self):
            return {
                "capability_schema_id": self.capability_schema_id,
                "build_capability_profile_id": self.build_capability_profile_id,
                "army_blueprint_hash": self.army_blueprint_hash,
                "pressure_profile": {},
                "capability_scores": {},
            }

    class _FakeContext:
        matchup_context_id = "matchup_context:test"
        field_distribution_id = field_distribution.field_distribution_id
        event_policy_id = event_policy.event_policy_id
        rules_bundle_id = field_distribution.rules_bundle_id

        def to_dict(self):
            return {
                "matchup_context_id": self.matchup_context_id,
                "field_distribution_id": self.field_distribution_id,
                "event_policy_id": self.event_policy_id,
                "rules_bundle_id": self.rules_bundle_id,
                "round_count": 5,
            }

    import warhammer40k_ai.ml.evaluation_pipeline as pipeline

    monkeypatch.setattr(pipeline, "run_headless_self_play_stage", _fake_self_play_stage(records))
    monkeypatch.setattr(pipeline, "audit_replay_sessions", _fake_replay_pass)
    monkeypatch.setattr(pipeline, "compile_build_capability_profile", lambda *args, **kwargs: _FakeProfile())
    monkeypatch.setattr(pipeline, "compile_matchup_context", lambda *args, **kwargs: _FakeContext())

    result = run_tournament_roster_evaluation(
        policy_bundle_source=str(bundle_path),
        models_root=models_root,
        player1_army="army_lists/chaos_test.txt",
        player2_army="army_lists/aeldari_test.txt",
        army_blueprint=str(blueprint_path),
        event_policy=str(event_policy_path),
        field_distribution=str(field_path),
        rules_data_dir=Path(__file__).resolve().parents[2] / "wahapedia_data",
        report_dir=tmp_path / "report",
        games=1,
        evaluation_mode=HEADLESS_FIXED_EVALUATION_MODE,
    )

    assert result["success"] is True
    roster_evaluation = dict(result["summary"]["roster_evaluation"])
    assert roster_evaluation["build_capability_profile_id"] == "build_capability_profile:test"
    assert roster_evaluation["matchup_context_id"] == "matchup_context:test"
    assert Path(roster_evaluation["roster_context_path"]).is_file()
    assert Path(roster_evaluation["muster_record_path"]).is_file()
    assert Path(roster_evaluation["mustering_manifest_path"]).is_file()
    assert roster_evaluation["lineage"]["rules_bundle_id"] == "rules_bundle:test_bundle"
    assert roster_evaluation["lineage"]["policy_bundle_id"] == "policy_bundle:heuristic_eval_v1"

    muster_record = json.loads(Path(roster_evaluation["muster_record_path"]).read_text(encoding="utf-8"))
    mustering_manifest = json.loads(
        Path(roster_evaluation["mustering_manifest_path"]).read_text(encoding="utf-8")
    )
    assert validate_muster_record(muster_record) == []
    assert validate_mustering_manifest(mustering_manifest) == []
    assert muster_record["record_id"] == roster_evaluation["muster_record_id"]
    assert muster_record["rules_bundle_id"] == "rules_bundle:test_bundle"
    assert muster_record["policy_bundle_id"] == "policy_bundle:heuristic_eval_v1"
    assert muster_record["capability_schema_id"] == "capability_schema:build_capability_v1"
    assert muster_record["build_capability_profile_id"] == "build_capability_profile:test"
    assert muster_record["descriptor_bundle_id"] == "descriptor_bundle:test_bundle"
    assert muster_record["descriptor_provenance"]["policy_bundle_lineage"]["descriptor_bundle_scope"]["ids"] == [
        "descriptor_bundle:test_bundle"
    ]
    assert mustering_manifest["total_records"] == 1
    assert mustering_manifest["record_ids"] == [muster_record["record_id"]]
    assert mustering_manifest["rules_bundle_ids"] == ["rules_bundle:test_bundle"]


def test_evaluate_policy_bundle_cli_returns_nonzero_on_failed_evaluation(monkeypatch, tmp_path: Path) -> None:
    mod = _load_script_module("evaluate_policy_bundle.py")

    monkeypatch.setattr(
        mod,
        "run_policy_bundle_evaluation",
        lambda **_kwargs: {
            "success": False,
            "report_dir": str(tmp_path / "report"),
            "summary_path": str(tmp_path / "report" / "summary.json"),
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_policy_bundle.py",
            "--policy-bundle",
            "policy_bundle:test_bundle",
        ],
    )

    assert mod.main() == 1


def test_evaluate_tournament_roster_cli_returns_nonzero_on_failed_evaluation(monkeypatch, tmp_path: Path) -> None:
    mod = _load_script_module("evaluate_tournament_roster.py")

    monkeypatch.setattr(
        mod,
        "run_tournament_roster_evaluation",
        lambda **_kwargs: {
            "success": False,
            "report_dir": str(tmp_path / "report"),
            "summary_path": str(tmp_path / "report" / "summary.json"),
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_tournament_roster.py",
            "--policy-bundle",
            "policy_bundle:test_bundle",
            "--player1-army",
            "army_lists/chaos_test.txt",
            "--player2-army",
            "army_lists/aeldari_test.txt",
            "--army-blueprint",
            str(tmp_path / "blueprint.json"),
            "--event-policy",
            str(tmp_path / "event_policy.json"),
            "--field-distribution",
            str(tmp_path / "field.json"),
            "--rules-data-dir",
            str(Path(__file__).resolve().parents[2] / "wahapedia_data"),
        ],
    )

    assert mod.main() == 1
