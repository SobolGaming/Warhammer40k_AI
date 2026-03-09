from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import numpy as np

from .decision_kinds import (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)
from .deployment_ranker import (
    DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS,
    DEPLOYMENT_RANKER_MODEL_TYPE,
    DeploymentRankerModel,
    deployment_ranker_feature_vector,
)


DEFAULT_DEPLOYMENT_RANKING_DECISION_TYPES: tuple[str, ...] = (
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SCOUT_MOVE,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
)

DEFAULT_DEPLOYMENT_RANKING_CANDIDATE_KINDS: tuple[str, ...] = (
    "deployment_zone",
    "deployment_commit_order",
    "deployment_reserves",
    "deployment_scout",
    "deployment_move",
    "noop",
)


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_records_from_document(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        return [dict(item or {}) for item in list(document or []) if isinstance(item, dict)]
    if isinstance(document, dict):
        records = document.get("records")
        if isinstance(records, list):
            return [dict(item or {}) for item in list(records or []) if isinstance(item, dict)]
        return [dict(document)]
    raise ValueError("Input payload must be a record dict, list of records, or {\"records\": [...]} object.")


def build_deployment_ranking_dataset(
    records: Iterable[dict[str, Any]],
    *,
    decision_types: Iterable[str] | None = None,
    candidate_kinds: Iterable[str] | None = None,
    feature_keys: Iterable[str] | None = None,
    require_valid: bool = True,
    minimum_legal_candidates: int = 2,
) -> dict[str, Any]:
    decision_type_set = {
        str(value or "").strip()
        for value in list(decision_types or DEFAULT_DEPLOYMENT_RANKING_DECISION_TYPES)
        if str(value or "").strip()
    }
    candidate_kind_set = {
        str(value or "").strip()
        for value in list(candidate_kinds or DEFAULT_DEPLOYMENT_RANKING_CANDIDATE_KINDS)
        if str(value or "").strip()
    }
    ordered_feature_keys = tuple(
        str(key)
        for key in list(feature_keys or DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS)
        if str(key or "").strip()
    )
    if not ordered_feature_keys:
        raise ValueError("feature_keys must contain at least one feature name.")

    decisions: list[dict[str, Any]] = []
    total_input_records = 0
    total_candidate_rows = 0
    skipped_missing_choice = 0
    skipped_low_candidate_count = 0
    skipped_not_valid = 0
    skipped_decision_type = 0
    skipped_candidate_kind = 0
    skipped_non_deployment_move = 0

    for record in list(records or []):
        item = dict(record or {})
        total_input_records += 1
        decision_type = str(item.get("decision_type", "") or "")
        if decision_type not in decision_type_set:
            skipped_decision_type += 1
            continue
        if decision_type == DECISION_MOVE_UNIT:
            context = dict(item.get("context", {}) or {})
            placement_kind = str(context.get("placement_kind", "") or "").strip().lower()
            if placement_kind != "deployment":
                skipped_non_deployment_move += 1
                continue
        if require_valid and not bool(item.get("valid", False)):
            skipped_not_valid += 1
            continue

        chosen_action_id = str(item.get("chosen_action_id", "") or "")
        if not chosen_action_id:
            skipped_missing_choice += 1
            continue

        candidates = list(item.get("candidates", []) or [])
        raw_mask = list(item.get("mask", []) or [])
        legal_rows: list[dict[str, Any]] = []
        for idx, candidate in enumerate(candidates):
            candidate_payload = dict(candidate or {})
            action_id = str(candidate_payload.get("action_id", "") or "")
            if not action_id:
                continue
            if idx < len(raw_mask) and not bool(raw_mask[idx]):
                continue
            metadata = dict(candidate_payload.get("metadata", {}) or {})
            candidate_kind = str(metadata.get("candidate_kind", "") or "").strip()
            if candidate_kind_set and candidate_kind not in candidate_kind_set:
                skipped_candidate_kind += 1
                continue
            legal_rows.append(
                {
                    "action_id": action_id,
                    "is_chosen": bool(action_id == chosen_action_id),
                    "candidate_kind": candidate_kind,
                    "features": deployment_ranker_feature_vector(metadata, feature_keys=ordered_feature_keys),
                }
            )

        if len(legal_rows) < max(2, int(minimum_legal_candidates)):
            skipped_low_candidate_count += 1
            continue
        if not any(bool(row.get("is_chosen", False)) for row in legal_rows):
            skipped_missing_choice += 1
            continue

        decisions.append(
            {
                "decision_id": str(item.get("decision_id", "") or ""),
                "decision_type": decision_type,
                "game_id": str(item.get("game_id", "") or ""),
                "player_id": str(item.get("player_id", "") or ""),
                "chosen_action_id": chosen_action_id,
                "candidates": legal_rows,
                "reward_target": _safe_float(item.get("reward_target"), default=0.0),
            }
        )
        total_candidate_rows += int(len(legal_rows))

    return {
        "schema_version": "1.0.0",
        "dataset_type": "deployment_candidate_ranking",
        "generated_at_utc": _utc_timestamp(),
        "decision_types": sorted(decision_type_set),
        "candidate_kinds": sorted(candidate_kind_set),
        "feature_keys": list(ordered_feature_keys),
        "total_input_records": int(total_input_records),
        "total_rank_decisions": int(len(decisions)),
        "total_candidate_rows": int(total_candidate_rows),
        "skipped_not_target_decision_type": int(skipped_decision_type),
        "skipped_not_target_candidate_kind": int(skipped_candidate_kind),
        "skipped_non_deployment_move_records": int(skipped_non_deployment_move),
        "skipped_not_valid": int(skipped_not_valid),
        "skipped_missing_choice": int(skipped_missing_choice),
        "skipped_low_candidate_count": int(skipped_low_candidate_count),
        "decisions": decisions,
    }


def _sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def _candidate_matrix_for_decision(
    decision: dict[str, Any],
    *,
    feature_keys: tuple[str, ...],
) -> tuple[np.ndarray, int]:
    rows = list(decision.get("candidates", []) or [])
    matrix: list[list[float]] = []
    chosen_index = -1
    for idx, row in enumerate(rows):
        features = dict(row.get("features", {}) or {})
        vector = [_safe_float(features.get(key), default=0.0) for key in feature_keys]
        matrix.append(vector)
        if bool(row.get("is_chosen", False)):
            chosen_index = idx
    if chosen_index < 0:
        raise ValueError("Each dataset decision must include exactly one chosen candidate.")
    return np.asarray(matrix, dtype=np.float64), int(chosen_index)


def train_deployment_ranker_model(
    dataset: dict[str, Any],
    *,
    epochs: int = 120,
    learning_rate: float = 0.05,
    l2_weight: float = 1e-4,
    seed: int = 0,
) -> DeploymentRankerModel:
    payload = dict(dataset or {})
    feature_keys = tuple(str(key) for key in list(payload.get("feature_keys", []) or []) if str(key or "").strip())
    if not feature_keys:
        raise ValueError("Dataset is missing feature_keys.")
    decisions = [dict(item or {}) for item in list(payload.get("decisions", []) or []) if isinstance(item, dict)]
    if not decisions:
        raise ValueError("Dataset has no trainable decisions.")

    decision_matrices: list[np.ndarray] = []
    chosen_indices: list[int] = []
    candidate_kinds: set[str] = set()
    decision_types: set[str] = set()
    for decision in decisions:
        matrix, chosen_index = _candidate_matrix_for_decision(decision, feature_keys=feature_keys)
        if matrix.shape[0] < 2:
            continue
        decision_matrices.append(matrix)
        chosen_indices.append(chosen_index)
        decision_types.add(str(decision.get("decision_type", "") or ""))
        for candidate in list(decision.get("candidates", []) or []):
            kind = str(dict(candidate or {}).get("candidate_kind", "") or "").strip()
            if kind:
                candidate_kinds.add(kind)
    if not decision_matrices:
        raise ValueError("Dataset has no decisions with at least two candidates.")

    all_candidate_vectors = np.vstack(decision_matrices)
    mean = np.mean(all_candidate_vectors, axis=0)
    std = np.std(all_candidate_vectors, axis=0)
    std = np.where(std > 1e-9, std, 1.0)

    pairwise_vectors: list[np.ndarray] = []
    pairwise_labels: list[float] = []
    normalized_matrices: list[np.ndarray] = []
    for matrix, chosen_index in zip(decision_matrices, chosen_indices):
        normalized = (matrix - mean) / std
        normalized_matrices.append(normalized)
        chosen = normalized[chosen_index]
        for idx in range(normalized.shape[0]):
            if idx == chosen_index:
                continue
            other = normalized[idx]
            pairwise_vectors.append(chosen - other)
            pairwise_labels.append(1.0)
            pairwise_vectors.append(other - chosen)
            pairwise_labels.append(0.0)
    if not pairwise_vectors:
        raise ValueError("Dataset must contain at least one positive/negative candidate pair.")

    x = np.vstack(pairwise_vectors)
    y = np.asarray(pairwise_labels, dtype=np.float64)
    rng = np.random.default_rng(int(seed))
    weights = rng.normal(0.0, 0.01, size=x.shape[1]).astype(np.float64)
    bias = 0.0

    total_epochs = max(1, int(epochs))
    lr = max(1e-5, float(learning_rate))
    l2 = max(0.0, float(l2_weight))
    sample_count = float(x.shape[0])
    for _epoch in range(total_epochs):
        logits = np.matmul(x, weights) + float(bias)
        probs = _sigmoid(logits)
        residual = probs - y
        grad_w = (np.matmul(x.T, residual) / sample_count) + (l2 * weights)
        grad_b = float(np.mean(residual))
        weights -= lr * grad_w
        bias -= lr * grad_b

    final_logits = np.matmul(x, weights) + float(bias)
    final_preds = (final_logits >= 0.0).astype(np.float64)
    pairwise_accuracy = float(np.mean(final_preds == y))

    top1_correct = 0
    for normalized, chosen_index in zip(normalized_matrices, chosen_indices):
        scores = np.matmul(normalized, weights) + float(bias)
        predicted = int(np.argmax(scores))
        if predicted == int(chosen_index):
            top1_correct += 1
    top1_accuracy = float(top1_correct / float(len(normalized_matrices)))

    metrics = {
        "pairwise_samples": int(x.shape[0]),
        "decisions_used": int(len(normalized_matrices)),
        "pairwise_accuracy": float(round(pairwise_accuracy, 6)),
        "top1_accuracy": float(round(top1_accuracy, 6)),
        "epochs": int(total_epochs),
        "learning_rate": float(lr),
        "l2_weight": float(l2),
    }

    return DeploymentRankerModel(
        model_type=DEPLOYMENT_RANKER_MODEL_TYPE,
        feature_keys=feature_keys,
        weights=tuple(float(value) for value in list(weights)),
        bias=float(bias),
        feature_mean=tuple(float(value) for value in list(mean)),
        feature_scale=tuple(float(value) for value in list(std)),
        decision_types=tuple(sorted(value for value in decision_types if value)),
        candidate_kinds=tuple(sorted(candidate_kinds)),
        created_at_utc=_utc_timestamp(),
        training_metrics=metrics,
    )
