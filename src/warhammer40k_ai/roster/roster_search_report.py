"""Serializable reports for deterministic roster search."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .army_build import ArmyBlueprint
from .build_capability_schema import json_safe


@dataclass(frozen=True)
class RosterSearchCandidateReport:
    candidate_id: str
    army_blueprint: ArmyBlueprint
    score: float
    utility_decomposition: dict[str, Any] = field(default_factory=dict)
    edit_trace: tuple[dict[str, Any], ...] = ()
    evaluation_summary: dict[str, Any] = field(default_factory=dict)
    validation_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "army_blueprint_hash": self.army_blueprint.army_blueprint_hash,
            "army_blueprint": self.army_blueprint.to_dict(),
            "score": float(self.score),
            "utility_decomposition": dict(json_safe(self.utility_decomposition or {})),
            "edit_trace": [dict(json_safe(item or {})) for item in self.edit_trace],
            "evaluation_summary": dict(json_safe(self.evaluation_summary or {})),
            "validation_summary": dict(json_safe(self.validation_summary or {})),
        }


@dataclass(frozen=True)
class RosterSearchIterationReport:
    iteration_index: int
    frontier_size: int
    candidate_count: int
    rejected_candidate_count: int
    best_candidate_id: str | None = None
    best_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration_index": int(self.iteration_index),
            "frontier_size": int(self.frontier_size),
            "candidate_count": int(self.candidate_count),
            "rejected_candidate_count": int(self.rejected_candidate_count),
            "best_candidate_id": self.best_candidate_id,
            "best_score": None if self.best_score is None else float(self.best_score),
        }


@dataclass(frozen=True)
class RosterSearchReport:
    strategy: str
    random_seed: int | None
    seed_blueprint: ArmyBlueprint
    top_candidates: tuple[RosterSearchCandidateReport, ...]
    iterations: tuple[RosterSearchIterationReport, ...] = ()
    generated_candidate_count: int = 0
    legal_candidate_count: int = 0
    rejected_candidate_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": str(self.strategy or ""),
            "random_seed": self.random_seed,
            "seed_blueprint_hash": self.seed_blueprint.army_blueprint_hash,
            "seed_blueprint": self.seed_blueprint.to_dict(),
            "top_candidates": [candidate.to_dict() for candidate in self.top_candidates],
            "iterations": [iteration.to_dict() for iteration in self.iterations],
            "generated_candidate_count": int(self.generated_candidate_count),
            "legal_candidate_count": int(self.legal_candidate_count),
            "rejected_candidate_count": int(self.rejected_candidate_count),
            "metadata": dict(json_safe(self.metadata or {})),
        }


__all__ = [
    "RosterSearchCandidateReport",
    "RosterSearchIterationReport",
    "RosterSearchReport",
]
