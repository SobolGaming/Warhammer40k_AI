"""Pathing package."""

from .dynamic_overlay import (
    DynamicModelBlocker,
    DynamicOverlay,
    build_dynamic_overlay,
    query_enemy_blockers,
    query_enemy_engagement_masks,
    query_friendly_blockers,
)
from .rules_profile import build_movement_profile
from .surfaces import (
    ELEVATED_LAYER_KIND,
    GROUND_LAYER_KIND,
    GROUND_SURFACE_ID,
    RUINS_LAYER_KIND,
    SupportSurface,
    SupportValidationResult,
    extract_ground_transit_obstacles,
    extract_support_surfaces,
    resolve_support_surface_at_position,
    terrain_ignored_for_ground_transit,
    validate_pose_support,
    validate_pose_support_on_surface,
)
from .types import ConnectorId, MovementProfile, SurfaceId
from .world_snapshot import (
    WorldSnapshot,
    build_world_snapshot,
    movement_profile_signature,
    support_surface_revision,
    terrain_revision,
)

__all__ = [
    "ConnectorId",
    "DynamicModelBlocker",
    "DynamicOverlay",
    "ELEVATED_LAYER_KIND",
    "GROUND_LAYER_KIND",
    "GROUND_SURFACE_ID",
    "MovementProfile",
    "RUINS_LAYER_KIND",
    "SupportSurface",
    "SupportValidationResult",
    "SurfaceId",
    "WorldSnapshot",
    "build_dynamic_overlay",
    "build_movement_profile",
    "build_world_snapshot",
    "extract_ground_transit_obstacles",
    "extract_support_surfaces",
    "movement_profile_signature",
    "query_enemy_blockers",
    "query_enemy_engagement_masks",
    "query_friendly_blockers",
    "resolve_support_surface_at_position",
    "support_surface_revision",
    "terrain_ignored_for_ground_transit",
    "terrain_revision",
    "validate_pose_support",
    "validate_pose_support_on_surface",
]
