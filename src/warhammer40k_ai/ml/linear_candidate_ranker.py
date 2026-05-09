from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

from ..engine.ai_domain_agents import legal_candidates
from ..engine.candidate_semantics import SEMANTIC_NUMERIC_KEYS
from ..engine.decisions import CandidateAction, DecisionRequest


LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID = "candidate_ranker_linear_v1"
LINEAR_CANDIDATE_RANKER_MODEL_SCHEMA_ID = "candidate_ranker_linear_model:v1"
LINEAR_CANDIDATE_RANKER_FEATURE_SCHEMA_ID = "feature_schema:decision_candidate_semantics_v2"
DEFAULT_HASH_BUCKET_COUNT = 512

_EXTRA_NUMERIC_METADATA_KEYS = (
    "reserve_denial_delta",
    "screen_integrity_delta",
    "countercharge_coverage_delta",
    "aura_connectivity_delta",
    "lookahead_total_value",
)

_DECLINE_ACTIONS = {"decline", "none", "noop", "pass", "skip"}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(result):
        return float(default)
    return float(result)


def _stable_hash_bucket(feature_name: str, feature_value: object, *, hash_bucket_count: int) -> str:
    encoded = f"{feature_name}={feature_value}".encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    bucket = int(digest[:16], 16) % max(1, int(hash_bucket_count))
    return f"hash:{bucket:04d}"


def _add_hash_feature(
    features: dict[str, float],
    feature_name: str,
    feature_value: object,
    *,
    hash_bucket_count: int,
    value: float = 1.0,
) -> None:
    text = str(feature_value or "").strip()
    if not text:
        return
    key = _stable_hash_bucket(feature_name, text, hash_bucket_count=hash_bucket_count)
    features[key] = float(features.get(key, 0.0) + float(value))


def _candidate_payload(candidate: CandidateAction | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(candidate, CandidateAction):
        return {
            "action_id": str(getattr(candidate, "action_id", "") or ""),
            "params": dict(getattr(candidate, "params", {}) or {}),
            "metadata": dict(getattr(candidate, "metadata", {}) or {}),
        }
    data = dict(candidate or {})
    return {
        "action_id": str(data.get("action_id", "") or ""),
        "params": dict(data.get("params", {}) or {}),
        "metadata": dict(data.get("metadata", {}) or {}),
    }


def _candidate_requests_decline(params: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    action = str(params.get("action", params.get("choice", "")) or "").strip().lower()
    candidate_kind = str(metadata.get("candidate_kind", "") or "").strip().lower()
    return (
        action in _DECLINE_ACTIONS
        or candidate_kind in _DECLINE_ACTIONS
        or bool(params.get("skip", False))
        or bool(params.get("skipped", False))
        or params.get("choice") is False
    )


def candidate_feature_map(
    *,
    decision_type: str,
    candidate: CandidateAction | Mapping[str, Any],
    candidate_index: int,
    candidate_count: int,
    legal_count: int,
    phase: str = "",
    request_context: Mapping[str, Any] | None = None,
    hash_bucket_count: int = DEFAULT_HASH_BUCKET_COUNT,
) -> dict[str, float]:
    payload = _candidate_payload(candidate)
    params = dict(payload.get("params", {}) or {})
    metadata = dict(payload.get("metadata", {}) or {})
    count = max(1, int(candidate_count or 1))
    legal = max(1, int(legal_count or 1))
    index = max(0, int(candidate_index or 0))
    features: dict[str, float] = {
        "bias": 1.0,
        "candidate_index_norm": float(index / max(1, count - 1)),
        "candidate_count_log": float(math.log1p(count)),
        "legal_count_log": float(math.log1p(legal)),
    }
    if index == 0:
        features["is_first_candidate"] = 1.0
    if index == count - 1:
        features["is_last_candidate"] = 1.0
    if _candidate_requests_decline(params, metadata):
        features["requests_decline"] = 1.0

    for key in (*SEMANTIC_NUMERIC_KEYS, *_EXTRA_NUMERIC_METADATA_KEYS):
        if key in metadata:
            value = _safe_float(metadata.get(key), default=0.0)
            if value:
                features[f"num:{key}"] = value

    for key, value in sorted(metadata.items()):
        if key in SEMANTIC_NUMERIC_KEYS or key in _EXTRA_NUMERIC_METADATA_KEYS:
            continue
        if isinstance(value, bool):
            if value:
                features[f"meta_bool:{key}"] = 1.0
            continue
        if isinstance(value, (int, float)):
            numeric = _safe_float(value, default=0.0)
            if numeric and len(str(key)) <= 80:
                features[f"meta_num:{key}"] = numeric

    context = dict(request_context or {})
    # Runtime entity ids are intentionally excluded here. They are replay-stable
    # within one game but not transferable training features across generated games.
    categorical_values = {
        "decision_type": str(decision_type or ""),
        "phase": str(phase or context.get("phase", "") or context.get("phase_step", "") or ""),
        "candidate_kind": str(metadata.get("candidate_kind", "") or ""),
        "metadata.label": str(metadata.get("label", "") or ""),
        "semantic_projection_kind": str(metadata.get("semantic_projection_kind", "") or ""),
        "params.action": str(params.get("action", "") or ""),
        "params.action_type": str(params.get("action_type", "") or ""),
        "params.ability_key": str(params.get("ability_key", "") or ""),
        "params.ability_name": str(params.get("ability_name", "") or ""),
        "params.card_name": str(params.get("card_name", "") or ""),
        "params.choice": str(params.get("choice", "") or ""),
        "params.choice_key": str(params.get("choice_key", "") or ""),
        "params.keyword": str(params.get("keyword", "") or ""),
        "params.movement_type": str(params.get("movement_type", "") or ""),
        "params.selection_kind": str(params.get("selection_kind", "") or ""),
        "params.stratagem_name": str(params.get("stratagem_name", "") or ""),
        "params.tool_id": str(params.get("tool_id", "") or ""),
        "params.tool_type": str(params.get("tool_type", "") or ""),
        "context.ability": str(context.get("ability", "") or ""),
        "context.ability_name": str(context.get("ability_name", "") or ""),
        "context.movement_type": str(context.get("movement_type", "") or ""),
        "context.phase_step": str(context.get("phase_step", "") or ""),
        "context.placement_kind": str(context.get("placement_kind", "") or ""),
        "context.selection_purpose": str(context.get("selection_purpose", "") or ""),
    }
    combination = params.get("combination")
    if isinstance(combination, Mapping):
        categorical_values["params.combination_id"] = str(
            combination.get("combination_id", combination.get("id", "")) or ""
        )
        categorical_values["params.deployment_definition_id"] = str(
            combination.get("deployment_definition_id", "") or ""
        )
        categorical_values["params.mission_definition_id"] = str(
            combination.get("mission_definition_id", "") or ""
        )
    for key, value in sorted(categorical_values.items()):
        _add_hash_feature(features, key, value, hash_bucket_count=hash_bucket_count)
    return features


def score_feature_map(features: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total = 0.0
    weight_values = dict(weights or {})
    for key, value in dict(features or {}).items():
        weight = float(weight_values.get(key, 0.0) or 0.0)
        if weight:
            total += float(value) * weight
    return float(total)


@dataclass(frozen=True)
class LinearCandidateRanker:
    component_name: str
    decision_type_weights: Mapping[str, Mapping[str, float]]
    hash_bucket_count: int = DEFAULT_HASH_BUCKET_COUNT
    artifact_id: str = ""
    manifest_path: str = ""
    config_path: str = ""

    @classmethod
    def from_config_path(
        cls,
        path: str | Path,
        *,
        component_name: str,
        artifact_id: str = "",
        manifest_path: str = "",
    ) -> "LinearCandidateRanker":
        resolved_path = Path(path)
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Linear candidate-ranker config at {resolved_path} must be a JSON object.")
        if str(payload.get("model_schema_id", "") or "") != LINEAR_CANDIDATE_RANKER_MODEL_SCHEMA_ID:
            raise ValueError(
                f"Linear candidate-ranker config at {resolved_path} has unsupported model_schema_id "
                f"{payload.get('model_schema_id')!r}."
            )
        weights = {
            str(decision_type): {
                str(feature): _safe_float(weight)
                for feature, weight in dict(feature_weights or {}).items()
                if _safe_float(weight)
            }
            for decision_type, feature_weights in dict(payload.get("decision_type_weights", {}) or {}).items()
        }
        return cls(
            component_name=str(component_name or payload.get("component_name", "") or ""),
            decision_type_weights=weights,
            hash_bucket_count=int(payload.get("hash_bucket_count", DEFAULT_HASH_BUCKET_COUNT) or DEFAULT_HASH_BUCKET_COUNT),
            artifact_id=str(artifact_id or payload.get("artifact_id", "") or ""),
            manifest_path=str(manifest_path or ""),
            config_path=str(resolved_path),
        )

    def choose_action_id(self, request: DecisionRequest) -> str:
        candidates = list(getattr(request, "candidates", []) or [])
        mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
        legal_action_ids = {str(candidate.action_id) for candidate in legal_candidates(request)}
        if not legal_action_ids:
            return ""
        decision_type = str(getattr(request, "decision_type", "") or "")
        weights = dict(self.decision_type_weights.get(decision_type, {}) or {})
        if not weights:
            return ""
        legal_count = len(legal_action_ids)
        best_action_id = ""
        best_score = float("-inf")
        for index, candidate in enumerate(candidates):
            action_id = str(getattr(candidate, "action_id", "") or "")
            if not action_id or action_id not in legal_action_ids:
                continue
            if index < len(mask) and not mask[index]:
                continue
            features = candidate_feature_map(
                decision_type=decision_type,
                candidate=candidate,
                candidate_index=index,
                candidate_count=len(candidates),
                legal_count=legal_count,
                phase=str(dict(getattr(request, "context", {}) or {}).get("phase", "") or ""),
                request_context=dict(getattr(request, "context", {}) or {}),
                hash_bucket_count=self.hash_bucket_count,
            )
            score = score_feature_map(features, weights)
            if score > best_score or (score == best_score and (not best_action_id or action_id < best_action_id)):
                best_score = float(score)
                best_action_id = action_id
        return best_action_id


__all__ = [
    "DEFAULT_HASH_BUCKET_COUNT",
    "LINEAR_CANDIDATE_RANKER_ARCHITECTURE_ID",
    "LINEAR_CANDIDATE_RANKER_MODEL_SCHEMA_ID",
    "LinearCandidateRanker",
    "LINEAR_CANDIDATE_RANKER_FEATURE_SCHEMA_ID",
    "candidate_feature_map",
    "score_feature_map",
]
