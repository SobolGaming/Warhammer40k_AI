from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


MANIFEST_VERSION = "1.4.0"
PRE_ML_BASELINE_GATE_PROFILE_ID = "pre_ml_baseline_v1"
_RATIO_PRECISION = 6


@dataclass(frozen=True)
class TrainingDataGateProfile:
    gate_profile_id: str
    minimum_tier3_pretraining_records: int
    required_semantic_candidate_metadata_ratio: float
    required_relabel_status_ratio: float
    minimum_games_observed: int
    required_records_with_game_id_ratio: float
    minimum_tactical_decisions_per_game: int
    required_combat_or_scoring_active_game_ratio: float
    maximum_no_progress_game_ratio: float
    required_nontrivial_vp_game_ratio: float
    minimum_nontrivial_total_vp: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_profile_id": str(self.gate_profile_id or ""),
            "minimum_tier3_pretraining_records": int(self.minimum_tier3_pretraining_records),
            "required_semantic_candidate_metadata_ratio": float(self.required_semantic_candidate_metadata_ratio),
            "required_relabel_status_ratio": float(self.required_relabel_status_ratio),
            "minimum_games_observed": int(self.minimum_games_observed),
            "required_records_with_game_id_ratio": float(self.required_records_with_game_id_ratio),
            "minimum_tactical_decisions_per_game": int(self.minimum_tactical_decisions_per_game),
            "required_combat_or_scoring_active_game_ratio": float(
                self.required_combat_or_scoring_active_game_ratio
            ),
            "maximum_no_progress_game_ratio": float(self.maximum_no_progress_game_ratio),
            "required_nontrivial_vp_game_ratio": float(self.required_nontrivial_vp_game_ratio),
            "minimum_nontrivial_total_vp": int(self.minimum_nontrivial_total_vp),
        }


PRE_ML_BASELINE_GATE_PROFILE = TrainingDataGateProfile(
    gate_profile_id=PRE_ML_BASELINE_GATE_PROFILE_ID,
    minimum_tier3_pretraining_records=10000,
    required_semantic_candidate_metadata_ratio=1.0,
    required_relabel_status_ratio=1.0,
    minimum_games_observed=20,
    required_records_with_game_id_ratio=1.0,
    minimum_tactical_decisions_per_game=25,
    required_combat_or_scoring_active_game_ratio=0.8,
    maximum_no_progress_game_ratio=0.2,
    required_nontrivial_vp_game_ratio=0.8,
    minimum_nontrivial_total_vp=5,
)


def _round_ratio(value: float) -> float:
    return float(round(float(value), _RATIO_PRECISION))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return _round_ratio(float(numerator) / float(denominator))


def _safe_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_str_tuple(values: Iterable[Any] | None) -> tuple[str, ...]:
    return tuple(sorted({str(item) for item in list(values or []) if str(item)}))


def _resolve_gate_profile(profile_id: str) -> TrainingDataGateProfile:
    normalized = str(profile_id or PRE_ML_BASELINE_GATE_PROFILE_ID)
    if normalized == PRE_ML_BASELINE_GATE_PROFILE_ID:
        return PRE_ML_BASELINE_GATE_PROFILE
    raise ValueError(f"Unknown training-data gate profile id: {normalized}")


@dataclass(frozen=True)
class TrainingManifestSlice:
    rules_bundle_ids: tuple[str, ...] = ()
    descriptor_bundle_ids: tuple[str, ...] = ()
    mission_descriptor_ids: tuple[str, ...] = ()
    objective_descriptor_ids: tuple[str, ...] = ()
    terrain_descriptor_ids: tuple[str, ...] = ()
    deployment_descriptor_ids: tuple[str, ...] = ()
    army_build_descriptor_ids: tuple[str, ...] = ()
    tool_descriptor_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_bundle_ids": list(self.rules_bundle_ids),
            "descriptor_bundle_ids": list(self.descriptor_bundle_ids),
            "mission_descriptor_ids": list(self.mission_descriptor_ids),
            "objective_descriptor_ids": list(self.objective_descriptor_ids),
            "terrain_descriptor_ids": list(self.terrain_descriptor_ids),
            "deployment_descriptor_ids": list(self.deployment_descriptor_ids),
            "army_build_descriptor_ids": list(self.army_build_descriptor_ids),
            "tool_descriptor_ids": list(self.tool_descriptor_ids),
        }

    def is_empty(self) -> bool:
        return not any(
            (
                self.rules_bundle_ids,
                self.descriptor_bundle_ids,
                self.mission_descriptor_ids,
                self.objective_descriptor_ids,
                self.terrain_descriptor_ids,
                self.deployment_descriptor_ids,
                self.army_build_descriptor_ids,
                self.tool_descriptor_ids,
            )
        )


@dataclass(frozen=True)
class TrainingDataManifest:
    manifest_version: str
    generated_at_utc: str
    source_tag: str
    total_records: int
    rules_bundle_ids: tuple[str, ...]
    descriptor_bundle_ids: tuple[str, ...]
    mission_descriptor_ids: tuple[str, ...]
    objective_descriptor_ids: tuple[str, ...]
    terrain_descriptor_ids: tuple[str, ...]
    deployment_descriptor_ids: tuple[str, ...]
    army_build_descriptor_ids: tuple[str, ...]
    tool_descriptor_ids: tuple[str, ...]
    decision_type_counts: dict[str, int]
    coverage: dict[str, Any]
    gameplay_quality: dict[str, Any]
    gate_requirements: dict[str, Any]
    slice_filters: TrainingManifestSlice

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": str(self.manifest_version or ""),
            "generated_at_utc": str(self.generated_at_utc or ""),
            "source_tag": str(self.source_tag or ""),
            "total_records": int(self.total_records),
            "rules_bundle_ids": list(self.rules_bundle_ids),
            "descriptor_bundle_ids": list(self.descriptor_bundle_ids),
            "mission_descriptor_ids": list(self.mission_descriptor_ids),
            "objective_descriptor_ids": list(self.objective_descriptor_ids),
            "terrain_descriptor_ids": list(self.terrain_descriptor_ids),
            "deployment_descriptor_ids": list(self.deployment_descriptor_ids),
            "army_build_descriptor_ids": list(self.army_build_descriptor_ids),
            "tool_descriptor_ids": list(self.tool_descriptor_ids),
            "decision_type_counts": {str(key): int(value) for key, value in sorted(self.decision_type_counts.items())},
            "coverage": dict(self.coverage or {}),
            "gameplay_quality": dict(self.gameplay_quality or {}),
            "gate_requirements": dict(self.gate_requirements or {}),
            "slice_filters": self.slice_filters.to_dict(),
        }


__all__ = [
    "MANIFEST_VERSION",
    "PRE_ML_BASELINE_GATE_PROFILE",
    "PRE_ML_BASELINE_GATE_PROFILE_ID",
    "TrainingDataGateProfile",
    "TrainingDataManifest",
    "TrainingManifestSlice",
    "_normalize_str_tuple",
    "_ratio",
    "_resolve_gate_profile",
    "_safe_float",
]
