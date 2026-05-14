from __future__ import annotations

import json
from pathlib import Path

from warhammer40k_ai.engine.ai_policy_orchestrator import COMPONENT_MOVEMENT_RANKER, AIPolicyOrchestrator
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import CandidateAction, DecisionOption, DecisionRequest
from warhammer40k_ai.ml import (
    ArtifactManifestStore,
    JSONPolicyBundleLoader,
    LINEAR_CANDIDATE_RANKER_FEATURE_SCHEMA_ID,
    LinearCandidateRanker,
)
from warhammer40k_ai.ml.imitation_training import (
    LinearImitationTrainingConfig,
    _split_name,
    train_linear_imitation_candidate_rankers,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _record(decision_id: str, *, game_id: str) -> dict[str, object]:
    return {
        "decision_id": decision_id,
        "decision_type": DECISION_MOVE_UNIT,
        "game_id": game_id,
        "phase": "MOVEMENT",
        "request_context": {"movement_type": "normal"},
        "valid": True,
        "candidates": [
            {
                "action_id": f"{decision_id}:a",
                "params": {"unit_id": "u1"},
                "metadata": {
                    "projected_score_delta_next_window": 0.0,
                    "projected_control_delta": 0.0,
                },
            },
            {
                "action_id": f"{decision_id}:b",
                "params": {"unit_id": "u1"},
                "metadata": {
                    "projected_score_delta_next_window": 2.0,
                    "projected_control_delta": 1.0,
                },
            },
        ],
        "mask": [True, True],
        "chosen_action_id": f"{decision_id}:b",
    }


def test_linear_imitation_training_exports_artifact_bundle_and_split_metrics(tmp_path: Path) -> None:
    split_salt = "test_split"
    train_game = next(
        f"game:train:{index}"
        for index in range(100)
        if _split_name(f"game:train:{index}", validation_ratio=0.5, salt=split_salt) == "train"
    )
    validation_game = next(
        f"game:validation:{index}"
        for index in range(100)
        if _split_name(f"game:validation:{index}", validation_ratio=0.5, salt=split_salt) == "validation"
    )
    records_path = tmp_path / "records.json"
    manifest_path = tmp_path / "training_manifest.json"
    _write_json(
        records_path,
        [
            _record("train_d1", game_id=train_game),
            _record("train_d2", game_id=train_game),
            _record("validation_d1", game_id=validation_game),
        ],
    )
    _write_json(
        manifest_path,
        {
            "manifest_version": "1.4.0",
            "total_records": 3,
            "rules_bundle_ids": ["rules_bundle:test"],
        },
    )

    result = train_linear_imitation_candidate_rankers(
        LinearImitationTrainingConfig(
            records_path=records_path,
            training_manifest_path=manifest_path,
            models_root=tmp_path / "models",
            run_id="linear_imitation_test_v1",
            policy_bundle_id="policy_bundle:linear_imitation_test_v1",
            epochs=1,
            validation_ratio=0.5,
            split_salt=split_salt,
            hash_bucket_count=64,
        )
    )

    bundle_path = Path(result["policy_bundle_path"])
    assert bundle_path.is_file()
    assert Path(result["training_report_path"]).is_file()
    assert result["game_counts_by_split"]["train"] == 1
    assert result["game_counts_by_split"]["validation"] == 1
    assert result["validation"]["overall"]["examples"] == 1
    assert result["validation"]["overall"]["top1_accuracy"] == 1.0
    artifact_id = result["artifact_ids_by_component"][COMPONENT_MOVEMENT_RANKER]
    artifact_manifest_path = ArtifactManifestStore(tmp_path / "models").artifact_manifest_path(artifact_id)
    assert artifact_manifest_path.is_file()
    artifact_manifest = json.loads(artifact_manifest_path.read_text(encoding="utf-8"))
    assert artifact_manifest["feature_schema_id"] == LINEAR_CANDIDATE_RANKER_FEATURE_SCHEMA_ID

    bundle = JSONPolicyBundleLoader(manifest_store=ArtifactManifestStore(tmp_path / "models")).load_bundle(
        "policy_bundle:linear_imitation_test_v1"
    )
    ranker = bundle.resolve_component(COMPONENT_MOVEMENT_RANKER)
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id="p1",
        options=[
            DecisionOption.create("A", payload={"action_id": "runtime:a"}),
            DecisionOption.create("B", payload={"action_id": "runtime:b"}),
        ],
        candidates=[
            CandidateAction("runtime:a", params={"unit_id": "u1"}, metadata={"projected_score_delta_next_window": 0.0}),
            CandidateAction("runtime:b", params={"unit_id": "u1"}, metadata={"projected_score_delta_next_window": 2.0}),
        ],
        mask=[True, True],
        context={"movement_type": "normal"},
    )

    assert isinstance(ranker, LinearCandidateRanker)
    assert AIPolicyOrchestrator.from_policy_bundle(bundle).choose_action(request).action_id == "runtime:b"
