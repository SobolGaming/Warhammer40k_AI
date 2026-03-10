from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, TypeAlias

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
