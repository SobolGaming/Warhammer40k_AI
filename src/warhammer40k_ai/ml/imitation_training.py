from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
from typing import Any, Iterable, Mapping

from ..engine.ai_controller_router import AI_POLICY_COMPONENTS, COMPONENT_NO_AI, decision_component_for
from ..engine.decision_kinds import (
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
)
from .linear_candidate_ranker import (
    DEFAULT_HASH_BUCKET_COUNT,
    LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID,
    LINEAR_CANDIDATE_RANKER_MODEL_SCHEMA_ID,
    candidate_feature_map,
    score_feature_map,
)
from .record_stream import iter_records_from_json
from .registry import ArtifactManifest, ArtifactManifestStore, PolicyBundleManifest


DEFAULT_EXCLUDED_DECISION_TYPES = (
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
)
DEFAULT_EVENT_POLICY_ID = "event_policy:chapter_approved_10e_singles_v1"
DEFAULT_DESCRIPTOR_BUNDLE_ID = "descriptor_bundle:current"
DEFAULT_VERSION_ADAPTER_BOUNDARY_ID = "adapter:rules_conditioned_path:v1"


@dataclass(frozen=True)
class LinearImitationTrainingConfig:
    records_path: Path
    training_manifest_path: Path
    models_root: Path
    run_id: str
    policy_bundle_id: str
    epochs: int = 1
    learning_rate: float = 1.0
    validation_ratio: float = 0.2
    split_salt: str = "linear_imitation_split_v1"
    hash_bucket_count: int = DEFAULT_HASH_BUCKET_COUNT
    event_policy_id: str = DEFAULT_EVENT_POLICY_ID
    descriptor_bundle_id: str = DEFAULT_DESCRIPTOR_BUNDLE_ID
    version_adapter_boundary_id: str = DEFAULT_VERSION_ADAPTER_BOUNDARY_ID
    excluded_decision_types: tuple[str, ...] = DEFAULT_EXCLUDED_DECISION_TYPES


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _current_git_commit() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_repo_root(),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return str(completed.stdout or "").strip()
    return "0" * 40


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(payload or {}), indent=2, sort_keys=True, ensure_ascii=True),
        encoding="utf-8",
    )


def _split_ratio(game_id: str, *, salt: str) -> float:
    encoded = f"{salt}|{game_id}".encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    max_u64 = float(16**16 - 1)
    return float(int(digest[:16], 16) / max_u64)


def _split_name(game_id: str, *, validation_ratio: float, salt: str) -> str:
    ratio = max(0.0, min(1.0, float(validation_ratio)))
    if ratio <= 0.0:
        return "train"
    return "validation" if _split_ratio(game_id, salt=salt) < ratio else "train"


def _safe_decision_type(record: Mapping[str, Any]) -> str:
    return str(record.get("decision_type", "") or "").strip()


def _legal_indices(record: Mapping[str, Any]) -> list[int]:
    candidates = list(record.get("candidates", []) or [])
    mask = [bool(value) for value in list(record.get("mask", []) or [])]
    if len(mask) != len(candidates):
        mask = [True] * len(candidates)
    legal: list[int] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping):
            continue
        if index < len(mask) and not mask[index]:
            continue
        if str(dict(candidate).get("action_id", "") or ""):
            legal.append(index)
    return legal


def _record_game_id(record: Mapping[str, Any]) -> str:
    game_id = str(record.get("game_id", "") or "").strip()
    if game_id:
        return game_id
    return str(record.get("decision_id", "") or "unknown_game")


def _record_phase(record: Mapping[str, Any]) -> str:
    return str(record.get("phase", "") or dict(record.get("request_context", {}) or {}).get("phase", "") or "")


def _chosen_legal_index(record: Mapping[str, Any], legal_indices: Iterable[int]) -> int | None:
    chosen_action_id = str(record.get("chosen_action_id", "") or "")
    if not chosen_action_id:
        return None
    candidates = list(record.get("candidates", []) or [])
    for index in legal_indices:
        candidate = dict(candidates[index] or {})
        if str(candidate.get("action_id", "") or "") == chosen_action_id:
            return int(index)
    return None


def _features_for_index(
    record: Mapping[str, Any],
    *,
    index: int,
    legal_count: int,
    hash_bucket_count: int,
) -> dict[str, float]:
    candidates = list(record.get("candidates", []) or [])
    return candidate_feature_map(
        decision_type=_safe_decision_type(record),
        candidate=dict(candidates[index] or {}),
        candidate_index=int(index),
        candidate_count=len(candidates),
        legal_count=int(legal_count),
        phase=_record_phase(record),
        request_context=dict(record.get("request_context", {}) or {}),
        hash_bucket_count=int(hash_bucket_count),
    )


def _rank_legal_indices(
    record: Mapping[str, Any],
    *,
    legal_indices: list[int],
    weights: Mapping[str, float],
    hash_bucket_count: int,
) -> list[int]:
    candidates = list(record.get("candidates", []) or [])

    def _sort_key(index: int) -> tuple[float, str]:
        features = _features_for_index(
            record,
            index=index,
            legal_count=len(legal_indices),
            hash_bucket_count=hash_bucket_count,
        )
        action_id = str(dict(candidates[index] or {}).get("action_id", "") or "")
        return (-score_feature_map(features, weights), action_id)

    return sorted(legal_indices, key=_sort_key)


def _update_weights(
    weights: dict[str, float],
    *,
    chosen_features: Mapping[str, float],
    predicted_features: Mapping[str, float],
    learning_rate: float,
) -> None:
    feature_keys = set(chosen_features) | set(predicted_features)
    for key in sorted(feature_keys):
        delta = float(chosen_features.get(key, 0.0) or 0.0) - float(predicted_features.get(key, 0.0) or 0.0)
        if not delta:
            continue
        updated = float(weights.get(key, 0.0) or 0.0) + float(learning_rate) * delta
        if abs(updated) <= 1e-12:
            weights.pop(key, None)
        else:
            weights[key] = float(round(updated, 8))


def _metric_bucket() -> dict[str, Any]:
    return {
        "examples": 0,
        "top1_correct": 0,
        "top3_correct": 0,
    }


def _finalize_metric_bucket(bucket: Mapping[str, Any]) -> dict[str, Any]:
    examples = int(bucket.get("examples", 0) or 0)
    top1 = int(bucket.get("top1_correct", 0) or 0)
    top3 = int(bucket.get("top3_correct", 0) or 0)
    return {
        "examples": examples,
        "top1_correct": top1,
        "top1_accuracy": round(top1 / examples, 6) if examples else 0.0,
        "top3_correct": top3,
        "top3_accuracy": round(top3 / examples, 6) if examples else 0.0,
    }


def _record_is_trainable(
    record: Mapping[str, Any],
    *,
    excluded_decision_types: set[str],
) -> tuple[bool, str]:
    if not bool(record.get("valid", True)):
        return False, "invalid_record"
    decision_type = _safe_decision_type(record)
    if not decision_type:
        return False, "missing_decision_type"
    if decision_type in excluded_decision_types:
        return False, "excluded_decision_type"
    component = decision_component_for(decision_type, dict(record.get("request_context", {}) or {}))
    if component == COMPONENT_NO_AI:
        return False, "no_ai_component"
    legal_indices = _legal_indices(record)
    if len(legal_indices) < 2:
        return False, "fewer_than_two_legal_candidates"
    if _chosen_legal_index(record, legal_indices) is None:
        return False, "chosen_action_not_legal"
    return True, ""


def _train_epoch(
    config: LinearImitationTrainingConfig,
    *,
    weights_by_decision_type: dict[str, dict[str, float]],
    components_by_decision_type: dict[str, set[str]],
    skipped: Counter[str],
    split_counts: Counter[str],
    game_ids_by_split: dict[str, set[str]],
) -> dict[str, Any]:
    updates = 0
    examples = 0
    mistakes_by_decision_type: Counter[str] = Counter()
    excluded = set(config.excluded_decision_types)
    for record in iter_records_from_json(config.records_path):
        trainable, skip_reason = _record_is_trainable(record, excluded_decision_types=excluded)
        if not trainable:
            skipped[skip_reason] += 1
            continue
        decision_type = _safe_decision_type(record)
        component = decision_component_for(decision_type, dict(record.get("request_context", {}) or {}))
        if component in AI_POLICY_COMPONENTS:
            components_by_decision_type.setdefault(decision_type, set()).add(component)
        game_id = _record_game_id(record)
        split = _split_name(game_id, validation_ratio=config.validation_ratio, salt=config.split_salt)
        split_counts[split] += 1
        game_ids_by_split.setdefault(split, set()).add(game_id)
        if split != "train":
            continue
        legal_indices = _legal_indices(record)
        chosen_index = _chosen_legal_index(record, legal_indices)
        if chosen_index is None:
            skipped["chosen_action_not_legal"] += 1
            continue
        weights = weights_by_decision_type.setdefault(decision_type, {})
        ranked = _rank_legal_indices(
            record,
            legal_indices=legal_indices,
            weights=weights,
            hash_bucket_count=config.hash_bucket_count,
        )
        predicted_index = ranked[0] if ranked else None
        examples += 1
        if predicted_index is not None and int(predicted_index) != int(chosen_index):
            chosen_features = _features_for_index(
                record,
                index=int(chosen_index),
                legal_count=len(legal_indices),
                hash_bucket_count=config.hash_bucket_count,
            )
            predicted_features = _features_for_index(
                record,
                index=int(predicted_index),
                legal_count=len(legal_indices),
                hash_bucket_count=config.hash_bucket_count,
            )
            _update_weights(
                weights,
                chosen_features=chosen_features,
                predicted_features=predicted_features,
                learning_rate=config.learning_rate,
            )
            updates += 1
            mistakes_by_decision_type[decision_type] += 1
    return {
        "examples": int(examples),
        "updates": int(updates),
        "mistake_rate": round(updates / examples, 6) if examples else 0.0,
        "mistakes_by_decision_type": dict(sorted(mistakes_by_decision_type.items())),
    }


def _evaluate_split(
    config: LinearImitationTrainingConfig,
    *,
    weights_by_decision_type: Mapping[str, Mapping[str, float]],
    split_name: str,
) -> dict[str, Any]:
    excluded = set(config.excluded_decision_types)
    overall = _metric_bucket()
    by_decision_type: dict[str, dict[str, Any]] = defaultdict(_metric_bucket)
    by_component: dict[str, dict[str, Any]] = defaultdict(_metric_bucket)
    skipped: Counter[str] = Counter()
    for record in iter_records_from_json(config.records_path):
        trainable, skip_reason = _record_is_trainable(record, excluded_decision_types=excluded)
        if not trainable:
            skipped[skip_reason] += 1
            continue
        game_id = _record_game_id(record)
        if _split_name(game_id, validation_ratio=config.validation_ratio, salt=config.split_salt) != split_name:
            continue
        decision_type = _safe_decision_type(record)
        component = decision_component_for(decision_type, dict(record.get("request_context", {}) or {}))
        legal_indices = _legal_indices(record)
        chosen_index = _chosen_legal_index(record, legal_indices)
        if chosen_index is None:
            skipped["chosen_action_not_legal"] += 1
            continue
        ranked = _rank_legal_indices(
            record,
            legal_indices=legal_indices,
            weights=dict(weights_by_decision_type.get(decision_type, {}) or {}),
            hash_bucket_count=config.hash_bucket_count,
        )
        top3 = set(ranked[:3])
        top1_correct = bool(ranked and int(ranked[0]) == int(chosen_index))
        top3_correct = int(chosen_index) in top3
        for bucket in (
            overall,
            by_decision_type[decision_type],
            by_component[component],
        ):
            bucket["examples"] = int(bucket.get("examples", 0) or 0) + 1
            if top1_correct:
                bucket["top1_correct"] = int(bucket.get("top1_correct", 0) or 0) + 1
            if top3_correct:
                bucket["top3_correct"] = int(bucket.get("top3_correct", 0) or 0) + 1
    return {
        "split": split_name,
        "overall": _finalize_metric_bucket(overall),
        "by_decision_type": {
            decision_type: _finalize_metric_bucket(bucket)
            for decision_type, bucket in sorted(by_decision_type.items())
        },
        "by_component": {
            component: _finalize_metric_bucket(bucket)
            for component, bucket in sorted(by_component.items())
        },
        "skipped": dict(sorted(skipped.items())),
    }


def _evaluate_splits(
    config: LinearImitationTrainingConfig,
    *,
    weights_by_decision_type: Mapping[str, Mapping[str, float]],
    split_names: Iterable[str],
) -> dict[str, dict[str, Any]]:
    wanted_splits = tuple(sorted({str(split or "") for split in split_names if str(split or "")}))
    overall = {split: _metric_bucket() for split in wanted_splits}
    by_decision_type: dict[str, dict[str, dict[str, Any]]] = {
        split: defaultdict(_metric_bucket) for split in wanted_splits
    }
    by_component: dict[str, dict[str, dict[str, Any]]] = {
        split: defaultdict(_metric_bucket) for split in wanted_splits
    }
    skipped: Counter[str] = Counter()
    excluded = set(config.excluded_decision_types)
    for record in iter_records_from_json(config.records_path):
        trainable, skip_reason = _record_is_trainable(record, excluded_decision_types=excluded)
        if not trainable:
            skipped[skip_reason] += 1
            continue
        game_id = _record_game_id(record)
        split = _split_name(game_id, validation_ratio=config.validation_ratio, salt=config.split_salt)
        if split not in overall:
            continue
        decision_type = _safe_decision_type(record)
        component = decision_component_for(decision_type, dict(record.get("request_context", {}) or {}))
        legal_indices = _legal_indices(record)
        chosen_index = _chosen_legal_index(record, legal_indices)
        if chosen_index is None:
            skipped["chosen_action_not_legal"] += 1
            continue
        ranked = _rank_legal_indices(
            record,
            legal_indices=legal_indices,
            weights=dict(weights_by_decision_type.get(decision_type, {}) or {}),
            hash_bucket_count=config.hash_bucket_count,
        )
        top3 = set(ranked[:3])
        top1_correct = bool(ranked and int(ranked[0]) == int(chosen_index))
        top3_correct = int(chosen_index) in top3
        for bucket in (
            overall[split],
            by_decision_type[split][decision_type],
            by_component[split][component],
        ):
            bucket["examples"] = int(bucket.get("examples", 0) or 0) + 1
            if top1_correct:
                bucket["top1_correct"] = int(bucket.get("top1_correct", 0) or 0) + 1
            if top3_correct:
                bucket["top3_correct"] = int(bucket.get("top3_correct", 0) or 0) + 1
    return {
        split: {
            "split": split,
            "overall": _finalize_metric_bucket(overall[split]),
            "by_decision_type": {
                decision_type: _finalize_metric_bucket(bucket)
                for decision_type, bucket in sorted(by_decision_type[split].items())
            },
            "by_component": {
                component: _finalize_metric_bucket(bucket)
                for component, bucket in sorted(by_component[split].items())
            },
            "skipped": dict(sorted(skipped.items())),
        }
        for split in wanted_splits
    }


def _scope(ids: Iterable[str]) -> dict[str, object]:
    normalized = sorted({str(item or "").strip() for item in list(ids or []) if str(item or "").strip()})
    if not normalized:
        normalized = ["rules_bundle:current"]
    return {
        "match_mode": "exact",
        "ids": normalized,
    }


def _training_manifest_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Training manifest at {path} must be a JSON object.")
    return dict(payload)


def _artifact_id_for(component_name: str, run_id: str) -> str:
    return f"artifact:{component_name}:linear_imitation:{run_id}"


def _write_artifacts_and_bundle(
    config: LinearImitationTrainingConfig,
    *,
    weights_by_decision_type: Mapping[str, Mapping[str, float]],
    components_by_decision_type: Mapping[str, set[str]],
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    manifest_store = ArtifactManifestStore(config.models_root)
    training_manifest = _training_manifest_payload(config.training_manifest_path)
    rules_bundle_ids = list(training_manifest.get("rules_bundle_ids", []) or ["rules_bundle:current"])
    training_manifest_hash = _sha256_file(config.training_manifest_path)
    git_commit = _current_git_commit()
    decision_types_by_component: dict[str, list[str]] = defaultdict(list)
    for decision_type in sorted(weights_by_decision_type):
        components = sorted(components_by_decision_type.get(decision_type, set()) or {decision_component_for(decision_type)})
        for component in components:
            if component not in AI_POLICY_COMPONENTS:
                continue
            decision_types_by_component[component].append(decision_type)

    artifact_ids_by_component: dict[str, str] = {}
    artifact_manifest_paths: dict[str, str] = {}
    config_paths: dict[str, str] = {}
    for component_name in sorted(decision_types_by_component):
        artifact_id = _artifact_id_for(component_name, config.run_id)
        artifact_dir = manifest_store.artifact_manifest_path(artifact_id).parent
        component_decision_types = sorted(decision_types_by_component[component_name])
        component_weights = {
            decision_type: dict(weights_by_decision_type.get(decision_type, {}) or {})
            for decision_type in component_decision_types
        }
        model_config = {
            "model_schema_id": LINEAR_CANDIDATE_RANKER_MODEL_SCHEMA_ID,
            "artifact_id": artifact_id,
            "component_name": component_name,
            "architecture_id": LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID,
            "hash_bucket_count": int(config.hash_bucket_count),
            "decision_types": component_decision_types,
            "decision_type_weights": component_weights,
            "trained_at_utc": _utc_timestamp(),
            "training": {
                "records_path": str(config.records_path),
                "training_manifest_path": str(config.training_manifest_path),
                "run_id": config.run_id,
                "epochs": int(config.epochs),
                "learning_rate": float(config.learning_rate),
                "validation_ratio": float(config.validation_ratio),
                "split_salt": str(config.split_salt),
                "excluded_decision_types": list(config.excluded_decision_types),
            },
        }
        config_path = artifact_dir / "config.json"
        _write_json(config_path, model_config)
        component_metrics = dict(dict(metrics.get("validation", {}) or {}).get("by_component", {}).get(component_name, {}) or {})
        component_metrics.update(
            {
                "run_id": config.run_id,
                "component_name": component_name,
                "decision_types": component_decision_types,
                "decision_type_count": len(component_decision_types),
            }
        )
        metrics_path = artifact_dir / "metrics.json"
        _write_json(metrics_path, component_metrics)
        artifact_manifest = {
            "artifact_manifest_schema_id": "artifact_manifest_schema:v1",
            "artifact_id": artifact_id,
            "family_id": "family:linear_imitation_candidate_ranker",
            "component_type": component_name,
            "tier": "tier3_action_ranker",
            "architecture_id": LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID,
            "feature_schema_id": "feature_schema:decision_candidate_semantics_v1",
            "capability_schema_id": "capability_schema:build_capability_v1",
            "training_manifest_path": str(config.training_manifest_path),
            "training_manifest_hash": training_manifest_hash,
            "rules_bundle_scope": _scope(rules_bundle_ids),
            "descriptor_bundle_scope": _scope([config.descriptor_bundle_id]),
            "version_adapter_boundary_id": str(config.version_adapter_boundary_id),
            "event_policy_scope": _scope([config.event_policy_id]),
            "git_commit": git_commit,
            "parent_artifact_ids": [],
            "metrics": component_metrics,
            "status": "experimental",
        }
        ArtifactManifest.from_dict(artifact_manifest)
        manifest_path = manifest_store.artifact_manifest_path(artifact_id)
        _write_json(manifest_path, artifact_manifest)
        artifact_ids_by_component[component_name] = artifact_id
        artifact_manifest_paths[component_name] = str(manifest_path)
        config_paths[component_name] = str(config_path)

    components: dict[str, dict[str, str]] = {}
    fallbacks: dict[str, list[str]] = {}
    for component_name in AI_POLICY_COMPONENTS:
        heuristic_id = f"heuristic:{component_name}:v1"
        artifact_id = artifact_ids_by_component.get(component_name)
        if artifact_id:
            components[component_name] = {
                "resolver_kind": "artifact",
                "resolver_ref": artifact_id,
            }
            fallbacks[component_name] = [heuristic_id]
        else:
            components[component_name] = {
                "resolver_kind": "heuristic",
                "resolver_ref": heuristic_id,
            }
    components["matchup_evaluator"] = {
        "resolver_kind": "heuristic",
        "resolver_ref": "heuristic:capability_matchup:v1",
    }
    components["playbook_selector"] = {
        "resolver_kind": "heuristic",
        "resolver_ref": "heuristic:identity_playbook:v1",
    }
    fallbacks["playbook_selector"] = ["heuristic:identity_playbook_fallback:v1"]
    bundle_manifest = {
        "policy_bundle_schema_id": "policy_bundle_schema:v1",
        "policy_bundle_id": str(config.policy_bundle_id),
        "controller_type": "headless_self_play",
        "rules_bundle_scope": _scope(rules_bundle_ids),
        "descriptor_bundle_scope": _scope([config.descriptor_bundle_id]),
        "event_policy_scope": _scope([config.event_policy_id]),
        "components": components,
        "fallbacks": fallbacks,
        "required_feature_schema_ids": [
            "feature_schema:decision_candidate_semantics_v1",
            "feature_schema:roster_matchup_v1",
        ],
        "required_capability_schema_ids": ["capability_schema:build_capability_v1"],
        "created_from_commit": git_commit,
    }
    PolicyBundleManifest.from_dict(bundle_manifest)
    bundle_path = manifest_store.bundle_manifest_path(config.policy_bundle_id)
    _write_json(bundle_path, bundle_manifest)
    return {
        "artifact_ids_by_component": artifact_ids_by_component,
        "artifact_manifest_paths": artifact_manifest_paths,
        "config_paths": config_paths,
        "policy_bundle_id": str(config.policy_bundle_id),
        "policy_bundle_path": str(bundle_path),
    }


def train_linear_imitation_candidate_rankers(config: LinearImitationTrainingConfig) -> dict[str, Any]:
    weights_by_decision_type: dict[str, dict[str, float]] = {}
    components_by_decision_type: dict[str, set[str]] = {}
    skipped: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    game_ids_by_split: dict[str, set[str]] = {"train": set(), "validation": set()}
    epoch_reports = []
    for _epoch in range(max(1, int(config.epochs))):
        epoch_reports.append(
            _train_epoch(
                config,
                weights_by_decision_type=weights_by_decision_type,
                components_by_decision_type=components_by_decision_type,
                skipped=skipped,
                split_counts=split_counts,
                game_ids_by_split=game_ids_by_split,
            )
        )
    split_metrics = _evaluate_splits(
        config,
        weights_by_decision_type=weights_by_decision_type,
        split_names=("train", "validation"),
    )
    train_metrics = split_metrics["train"]
    validation_metrics = split_metrics["validation"]
    weight_counts = {
        decision_type: len(dict(weights or {}))
        for decision_type, weights in sorted(weights_by_decision_type.items())
    }
    metrics = {
        "generated_at_utc": _utc_timestamp(),
        "run_id": config.run_id,
        "model_schema_id": LINEAR_CANDIDATE_RANKER_MODEL_SCHEMA_ID,
        "architecture_id": LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID,
        "records_path": str(config.records_path),
        "training_manifest_path": str(config.training_manifest_path),
        "epochs": int(config.epochs),
        "learning_rate": float(config.learning_rate),
        "validation_ratio": float(config.validation_ratio),
        "hash_bucket_count": int(config.hash_bucket_count),
        "split_counts": dict(sorted(split_counts.items())),
        "game_counts_by_split": {
            split: len(ids)
            for split, ids in sorted(game_ids_by_split.items())
        },
        "skipped": dict(sorted(skipped.items())),
        "epoch_reports": epoch_reports,
        "train": train_metrics,
        "validation": validation_metrics,
        "trained_decision_type_count": len(weights_by_decision_type),
        "weight_counts_by_decision_type": weight_counts,
        "total_weight_count": int(sum(weight_counts.values())),
    }
    artifact_report = _write_artifacts_and_bundle(
        config,
        weights_by_decision_type=weights_by_decision_type,
        components_by_decision_type=components_by_decision_type,
        metrics=metrics,
    )
    report_path = config.models_root / "reports" / config.run_id / "training_report.json"
    _write_json(report_path, {**metrics, **artifact_report})
    return {
        **metrics,
        **artifact_report,
        "training_report_path": str(report_path),
    }


__all__ = [
    "DEFAULT_EXCLUDED_DECISION_TYPES",
    "LinearImitationTrainingConfig",
    "train_linear_imitation_candidate_rankers",
]
