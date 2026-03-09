from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np

from .decisions import CandidateAction, DecisionRequest


DEPLOYMENT_RANKER_MODEL_TYPE = "deployment_linear_ranker_v1"

DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS: tuple[str, ...] = (
    "projected_score_delta_next_window",
    "projected_score_delta_round",
    "projected_deny_delta_next_window",
    "projected_control_delta",
    "projected_action_enablement_delta",
    "projected_exposure_delta",
    "projected_trade_ev",
    "cover_delta",
    "los_delta",
    "resource_delta",
    "reserve_denial_delta",
    "deep_strike_pressure_delta",
    "reserve_entry_lane_delta",
    "reserve_unit_slots_ratio",
    "reserve_points_ratio",
    "strategic_points_ratio",
    "los_tunnel_count",
    "hidden_staging_cell_count",
    "must_expose_to_advance_cell_count",
    "infantry_objective_approach_quality",
    "vehicle_objective_approach_quality",
    "screen_integrity_delta",
    "countercharge_coverage_delta",
    "aura_connectivity_delta",
    "projected_exposure_delta_if_enemy_goes_first",
    "projected_melee_staging_delta",
    "lookahead_immediate_value",
    "lookahead_worst_branch_value",
    "lookahead_followup_value",
    "lookahead_enemy_pressure",
    "lookahead_total_value",
)


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_feature_keys(feature_keys: Iterable[str] | None) -> tuple[str, ...]:
    keys: list[str] = []
    for key in list(feature_keys or []):
        text = str(key or "").strip()
        if not text:
            continue
        if text in keys:
            continue
        keys.append(text)
    if keys:
        return tuple(keys)
    return DEFAULT_DEPLOYMENT_RANKER_FEATURE_KEYS


def _vector_from_metadata(
    metadata: dict[str, Any],
    *,
    feature_keys: tuple[str, ...],
) -> np.ndarray:
    values = [_safe_float(dict(metadata or {}).get(key), default=0.0) for key in feature_keys]
    return np.asarray(values, dtype=np.float64)


def _normalize_vector(
    vector: np.ndarray,
    *,
    mean: np.ndarray,
    scale: np.ndarray,
) -> np.ndarray:
    safe_scale = np.where(scale > 1e-9, scale, 1.0)
    return (vector - mean) / safe_scale


@dataclass(frozen=True)
class DeploymentRankerModel:
    model_type: str
    feature_keys: tuple[str, ...]
    weights: tuple[float, ...]
    bias: float
    feature_mean: tuple[float, ...]
    feature_scale: tuple[float, ...]
    decision_types: tuple[str, ...]
    candidate_kinds: tuple[str, ...]
    created_at_utc: str
    training_metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_type": str(self.model_type or DEPLOYMENT_RANKER_MODEL_TYPE),
            "feature_keys": [str(key) for key in self.feature_keys],
            "weights": [float(value) for value in self.weights],
            "bias": float(self.bias),
            "normalization": {
                "mean": [float(value) for value in self.feature_mean],
                "scale": [float(value) for value in self.feature_scale],
            },
            "decision_types": [str(value) for value in self.decision_types],
            "candidate_kinds": [str(value) for value in self.candidate_kinds],
            "created_at_utc": str(self.created_at_utc or ""),
            "training_metrics": dict(self.training_metrics or {}),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "DeploymentRankerModel":
        data = dict(payload or {})
        model_type = str(data.get("model_type", DEPLOYMENT_RANKER_MODEL_TYPE) or DEPLOYMENT_RANKER_MODEL_TYPE)
        if model_type != DEPLOYMENT_RANKER_MODEL_TYPE:
            raise ValueError(
                f"Unsupported deployment ranker model_type {model_type!r}; expected {DEPLOYMENT_RANKER_MODEL_TYPE!r}."
            )

        feature_keys = _normalize_feature_keys(data.get("feature_keys"))
        weights = tuple(_safe_float(value) for value in list(data.get("weights", []) or []))
        if len(weights) != len(feature_keys):
            raise ValueError(
                "Deployment ranker model is invalid: weights length must match feature_keys length."
            )
        normalization = dict(data.get("normalization", {}) or {})
        mean = tuple(_safe_float(value) for value in list(normalization.get("mean", []) or []))
        scale = tuple(_safe_float(value, default=1.0) for value in list(normalization.get("scale", []) or []))
        if len(mean) != len(feature_keys) or len(scale) != len(feature_keys):
            raise ValueError(
                "Deployment ranker model is invalid: normalization vectors must match feature_keys length."
            )

        decision_types = tuple(
            sorted(
                {
                    str(item or "").strip()
                    for item in list(data.get("decision_types", []) or [])
                    if str(item or "").strip()
                }
            )
        )
        candidate_kinds = tuple(
            sorted(
                {
                    str(item or "").strip()
                    for item in list(data.get("candidate_kinds", []) or [])
                    if str(item or "").strip()
                }
            )
        )
        created_at_utc = str(data.get("created_at_utc", "") or "")
        if not created_at_utc:
            created_at_utc = _utc_timestamp()

        return cls(
            model_type=model_type,
            feature_keys=feature_keys,
            weights=weights,
            bias=_safe_float(data.get("bias"), default=0.0),
            feature_mean=mean,
            feature_scale=scale,
            decision_types=decision_types,
            candidate_kinds=candidate_kinds,
            created_at_utc=created_at_utc,
            training_metrics=dict(data.get("training_metrics", {}) or {}),
        )


class DeploymentCandidateRanker:
    def __init__(self, model: DeploymentRankerModel) -> None:
        self._model = model
        self._feature_keys = tuple(model.feature_keys)
        self._weights = np.asarray(list(model.weights), dtype=np.float64)
        self._mean = np.asarray(list(model.feature_mean), dtype=np.float64)
        self._scale = np.asarray(list(model.feature_scale), dtype=np.float64)
        self._decision_types = set(model.decision_types)
        self._candidate_kinds = set(model.candidate_kinds)

    @property
    def model(self) -> DeploymentRankerModel:
        return self._model

    @property
    def feature_keys(self) -> tuple[str, ...]:
        return self._feature_keys

    @classmethod
    def from_json_file(cls, path: str | Path) -> "DeploymentCandidateRanker":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(DeploymentRankerModel.from_dict(dict(payload or {})))

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self._model.to_dict(), indent=2, sort_keys=True, ensure_ascii=True),
            encoding="utf-8",
        )

    def score_candidate(
        self,
        request: DecisionRequest,
        candidate: CandidateAction,
    ) -> Optional[float]:
        decision_type = str(getattr(request, "decision_type", "") or "")
        if self._decision_types and decision_type not in self._decision_types:
            return None
        metadata = dict(getattr(candidate, "metadata", {}) or {})
        candidate_kind = str(metadata.get("candidate_kind", "") or "")
        if self._candidate_kinds and candidate_kind and candidate_kind not in self._candidate_kinds:
            return None
        if self._candidate_kinds and not candidate_kind:
            return None

        vector = _vector_from_metadata(metadata, feature_keys=self._feature_keys)
        normalized = _normalize_vector(vector, mean=self._mean, scale=self._scale)
        score = float(np.dot(normalized, self._weights) + float(self._model.bias))
        return score

    def choose_action_id(self, request: DecisionRequest) -> str:
        candidates = list(getattr(request, "candidates", []) or [])
        mask = [bool(value) for value in list(getattr(request, "mask", []) or [])]
        best_action_id = ""
        best_score = float("-inf")
        best_tie = ""
        for idx, candidate in enumerate(candidates):
            if idx < len(mask) and not bool(mask[idx]):
                continue
            score = self.score_candidate(request, candidate)
            if score is None:
                continue
            action_id = str(getattr(candidate, "action_id", "") or "")
            tie = action_id
            if (score > best_score) or (score == best_score and tie < best_tie):
                best_score = float(score)
                best_tie = tie
                best_action_id = action_id
        return best_action_id


def deployment_ranker_feature_vector(
    metadata: dict[str, Any],
    *,
    feature_keys: Iterable[str] | None = None,
) -> dict[str, float]:
    keys = _normalize_feature_keys(feature_keys)
    return {key: _safe_float(dict(metadata or {}).get(key), default=0.0) for key in keys}
