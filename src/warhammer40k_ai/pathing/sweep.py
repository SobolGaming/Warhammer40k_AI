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


def intersects_enemy_models(
    swept_shape: BaseGeometry,
    enemy_blockers: Iterable[object],
) -> bool:
    for blocker in enemy_blockers:
        blocker_shape = getattr(blocker, "footprint", None)
        if blocker_shape is None:
            continue
        if swept_shape.intersects(blocker_shape):
            return True
    return False


def list_models_moved_over(
    swept_shape: BaseGeometry,
    enemy_blockers: Iterable[object],
) -> tuple[str, ...]:
    model_ids: set[str] = set()
    for blocker in enemy_blockers:
        blocker_shape = getattr(blocker, "footprint", None)
        if blocker_shape is None:
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
    "swept_footprint",
]
