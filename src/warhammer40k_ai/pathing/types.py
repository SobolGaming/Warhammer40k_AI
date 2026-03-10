from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, TypeAlias

SurfaceId: TypeAlias = str
ConnectorId: TypeAlias = str


@dataclass(frozen=True)
class MovementProfile:
    """Pure movement capability snapshot derived from unit + move context."""

    movement_type_tag: str
    free_climb_height_inches: float
    can_ignore_vertical_distance: bool
    can_breach_ruins_walls: bool
    can_end_on_upper_surfaces: bool
    can_move_through_enemy_models: bool
    can_move_through_friendly_models: bool
    pivot_cost_mode: str
    engagement_buffer_rules: Mapping[str, object] = field(default_factory=dict)
    terrain_transition_rules: Mapping[str, object] = field(default_factory=dict)
    fall_back_interaction_rules: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, eq=False)
class Pose:
    x: float
    y: float
    z: float
    facing: float


@dataclass(frozen=True, eq=False)
class PathQuery:
    model: object
    target: tuple[float, float, float] | tuple[float, float]
    movement_type: object
    max_distance: float
    game_map: object
    target_unit: object = None
    target_units: tuple[object, ...] = ()
    moved_models_in_unit: tuple[object, ...] = ()
    debug_enabled: bool = False
    use_cache: bool = True
    prefer_constrained: bool = True
    enable_exact_refine: bool = True
    exact_refine_max_paths: int = 3
    exact_refine_safety_margin: float = 0.1
    goal_facing: Optional[float] = None


@dataclass(frozen=True, eq=False)
class PathResult:
    valid: bool
    poses: tuple[Pose, ...]
    waypoints: tuple[tuple[float, float, float], ...]
    distance_cost: float
    pivot_cost: float
    used_exact_refiner: bool
    moved_over_enemy_model_ids: tuple[str, ...] = ()
    failure_reason: Optional[str] = None
    debug_artifacts: Mapping[str, object] = field(default_factory=dict)

    def to_legacy_dict(self) -> dict[str, object]:
        return {
            "valid": bool(self.valid),
            "path": list(self.waypoints) if self.waypoints else [],
            "distance": float(self.distance_cost + self.pivot_cost),
            "reason": str(self.failure_reason or "Valid path found"),
            "moved_over_enemy_model_ids": list(self.moved_over_enemy_model_ids),
            "used_exact_refiner": bool(self.used_exact_refiner),
            "debug_artifacts": dict(self.debug_artifacts),
        }


@dataclass(frozen=True, eq=False)
class ValidationResult:
    valid: bool
    reason: str
    debug_artifacts: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, eq=False)
class SweepResult:
    moved_over_enemy_model_ids: tuple[str, ...]
    intersects_enemy_models: bool
    debug_artifacts: Mapping[str, object] = field(default_factory=dict)
