from __future__ import annotations

from math import ceil, pi
from typing import Iterable

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .types import Pose


def _normalize_angle(angle: float) -> float:
    two_pi = 2.0 * pi
    normalized = float(angle) % two_pi
    if normalized < 0.0:
        normalized += two_pi
    return normalized


def _shortest_angle_delta(source: float, target: float) -> float:
    delta = _normalize_angle(target) - _normalize_angle(source)
    if delta > pi:
        delta -= 2.0 * pi
    elif delta < -pi:
        delta += 2.0 * pi
    return float(delta)


def _sampled_pose_sequence(
    poses: tuple[Pose, ...],
    *,
    translation_step: float,
    rotation_step: float,
) -> tuple[Pose, ...]:
    if len(poses) <= 1:
        return poses

    sampled: list[Pose] = [poses[0]]
    for index in range(1, len(poses)):
        prev_pose = poses[index - 1]
        next_pose = poses[index]
        dx = float(next_pose.x) - float(prev_pose.x)
        dy = float(next_pose.y) - float(prev_pose.y)
        dz = float(next_pose.z) - float(prev_pose.z)
        linear = (dx * dx + dy * dy + dz * dz) ** 0.5
        yaw_delta = abs(_shortest_angle_delta(float(prev_pose.facing), float(next_pose.facing)))

        steps_linear = int(ceil(linear / max(0.05, float(translation_step))))
        steps_yaw = int(ceil(yaw_delta / max(0.05, float(rotation_step))))
        steps = max(1, steps_linear, steps_yaw)

        for step in range(1, steps + 1):
            blend = float(step) / float(steps)
            sampled.append(
                Pose(
                    x=float(prev_pose.x) + dx * blend,
                    y=float(prev_pose.y) + dy * blend,
                    z=float(prev_pose.z) + dz * blend,
                    facing=_normalize_angle(
                        float(prev_pose.facing)
                        + _shortest_angle_delta(float(prev_pose.facing), float(next_pose.facing)) * blend
                    ),
                )
            )
    return tuple(sampled)


def swept_footprint(
    poses: tuple[Pose, ...],
    model_base: object,
    *,
    translation_step: float = 0.25,
    rotation_step: float = pi / 18.0,
) -> BaseGeometry:
    if not poses:
        return model_base.get_base_shape()

    sampled_poses = _sampled_pose_sequence(
        poses,
        translation_step=float(translation_step),
        rotation_step=float(rotation_step),
    )
    shapes = tuple(
        model_base.get_base_shape_at(float(pose.x), float(pose.y), float(pose.facing))
        for pose in sampled_poses
    )
    return unary_union(shapes)


def sweep_vertical_segments(
    poses: tuple[Pose, ...],
    model_base: object,
) -> tuple[tuple[float, float], ...]:
    if not poses:
        return ()

    z_reference = float(getattr(model_base, "z", 0.0) or 0.0)
    z_offset_bottom = 0.0
    z_offset_top = 0.0
    volume_bounds_fn = getattr(model_base, "volume_z_bounds", None)
    if callable(volume_bounds_fn):
        z_bottom, z_top = volume_bounds_fn()
        z_offset_bottom = float(z_bottom) - z_reference
        z_offset_top = float(z_top) - z_reference
    else:
        model_height = float(getattr(model_base, "model_height", 0.0) or 0.0)
        z_offset_top = max(0.0, model_height)

    if len(poses) == 1:
        z_bottom = float(poses[0].z) + z_offset_bottom
        z_top = float(poses[0].z) + z_offset_top
        return ((min(z_bottom, z_top), max(z_bottom, z_top)),)

    segments: list[tuple[float, float]] = []
    for index in range(1, len(poses)):
        start = poses[index - 1]
        end = poses[index]
        start_bottom = float(start.z) + z_offset_bottom
        start_top = float(start.z) + z_offset_top
        end_bottom = float(end.z) + z_offset_bottom
        end_top = float(end.z) + z_offset_top
        seg_min = min(start_bottom, start_top, end_bottom, end_top)
        seg_max = max(start_bottom, start_top, end_bottom, end_top)
        segments.append((seg_min, seg_max))
    return tuple(segments)


def _blocker_vertical_overlap(
    blocker: object,
    vertical_segments: tuple[tuple[float, float], ...],
) -> bool:
    if not vertical_segments:
        return True
    z_bottom = float(getattr(blocker, "z_bottom", 0.0) or 0.0)
    z_top = float(getattr(blocker, "z_top", z_bottom) or z_bottom)
    if z_bottom > z_top:
        z_bottom, z_top = z_top, z_bottom
    for seg_min, seg_max in vertical_segments:
        if seg_max < z_bottom:
            continue
        if seg_min > z_top:
            continue
        return True
    return False


def intersects_enemy_models(
    swept_shape: BaseGeometry,
    enemy_blockers: Iterable[object],
    *,
    require_vertical_overlap: bool = False,
    vertical_segments: tuple[tuple[float, float], ...] = (),
) -> bool:
    for blocker in enemy_blockers:
        blocker_shape = getattr(blocker, "footprint", None)
        if blocker_shape is None:
            continue
        if require_vertical_overlap and not _blocker_vertical_overlap(blocker, vertical_segments):
            continue
        if swept_shape.intersects(blocker_shape):
            return True
    return False


def list_models_moved_over(
    swept_shape: BaseGeometry,
    enemy_blockers: Iterable[object],
    *,
    require_vertical_overlap: bool = False,
    vertical_segments: tuple[tuple[float, float], ...] = (),
) -> tuple[str, ...]:
    model_ids: set[str] = set()
    for blocker in enemy_blockers:
        blocker_shape = getattr(blocker, "footprint", None)
        if blocker_shape is None:
            continue
        if require_vertical_overlap and not _blocker_vertical_overlap(blocker, vertical_segments):
            continue
        if not swept_shape.intersects(blocker_shape):
            continue
        blocker_id = str(getattr(blocker, "model_id", "") or "")
        if blocker_id:
            model_ids.add(blocker_id)
    return tuple(sorted(model_ids))


__all__ = [
    "intersects_enemy_models",
    "list_models_moved_over",
    "sweep_vertical_segments",
    "swept_footprint",
]
