from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional

from shapely.ops import unary_union
from shapely.geometry import Point as ShapelyPoint


@dataclass(frozen=True)
class AuraScope:
    """
    Basic targeting scope for aura-like effects.
    This is intentionally small; higher-level rules can layer keyword/type predicates.
    """

    affects_friendly: bool = True
    affects_enemy: bool = False


def _base_shape(model) -> Optional[object]:
    try:
        mb = getattr(model, "model_base", None)
        if mb is None:
            return None
        return mb.get_base_shape()
    except Exception:
        return None


def distance_between_models_bases_3d(model_a, model_b) -> float:
    """
    Core measurement primitive for "within X" checks (non-Engagement-Range):
    - shortest straight-line distance between closest points of bases/hulls
    - vertical separation counts as base-plane separation (z vs z), not model height
    """
    a = getattr(model_a, "model_base", None)
    b = getattr(model_b, "model_base", None)
    if a is None or b is None:
        return float("inf")

    try:
        shape_a = a.get_base_shape()
        shape_b = b.get_base_shape()
        dxy = float(shape_a.distance(shape_b))
    except Exception:
        try:
            ax = float(getattr(a, "x", 0.0))
            ay = float(getattr(a, "y", 0.0))
            bx = float(getattr(b, "x", 0.0))
            by = float(getattr(b, "y", 0.0))
            dxy = float(math.hypot(ax - bx, ay - by))
        except Exception:
            dxy = float("inf")

    try:
        dz = abs(float(getattr(a, "z", 0.0)) - float(getattr(b, "z", 0.0)))
    except Exception:
        dz = 0.0

    return float(math.hypot(dxy, dz))


def distance_between_bases_3d(base_a, base_b) -> float:
    """Same as distance_between_models_bases_3d, but accepts Base objects directly."""
    if base_a is None or base_b is None:
        return float("inf")
    try:
        dxy = float(base_a.get_base_shape().distance(base_b.get_base_shape()))
    except Exception:
        dxy = float("inf")
    try:
        dz = abs(float(getattr(base_a, "z", 0.0)) - float(getattr(base_b, "z", 0.0)))
    except Exception:
        dz = 0.0
    return float(math.hypot(dxy, dz))


def horizontal_distance_between_bases_2d(base_a, base_b) -> float:
    """2D base-to-base edge distance (no vertical component)."""
    if base_a is None or base_b is None:
        return float("inf")
    return float(base_a.get_base_shape().distance(base_b.get_base_shape()))


def vertical_distance_between_bases(base_a, base_b) -> float:
    """Base-plane vertical separation (no model height)."""
    if base_a is None or base_b is None:
        return float("inf")
    return abs(float(getattr(base_a, "z", 0.0)) - float(getattr(base_b, "z", 0.0)))


def min_distance_between_units_3d(unit1, unit2, *, use_attached_aggregate: bool = True) -> float:
    """Return minimum 3D base distance between any alive model pair in two units."""
    if use_attached_aggregate:
        m1 = unit1.get_attached_unit_models()
        m2 = unit2.get_attached_unit_models()
    else:
        m1 = list(getattr(unit1, "models", []) or [])
        m2 = list(getattr(unit2, "models", []) or [])

    a1 = [m for m in m1 if getattr(m, "is_alive", True)]
    a2 = [m for m in m2 if getattr(m, "is_alive", True)]
    if not a1 or not a2:
        return float("inf")

    best = float("inf")
    for x in a1:
        for y in a2:
            d = distance_between_models_bases_3d(x, y)
            if d < best:
                best = d
    return float(best)


def unit_within_range_of_unit(
    source_unit,
    target_unit,
    radius: float,
    *,
    use_attached_aggregate: bool = True,
) -> bool:
    """Unit is 'within X' if ANY target model is within X of ANY source model."""
    try:
        r = float(radius)
    except Exception:
        return False
    if r < 0:
        return False

    try:
        if use_attached_aggregate:
            s_models = source_unit.get_attached_unit_models()
            t_models = target_unit.get_attached_unit_models()
        else:
            s_models = list(getattr(source_unit, "models", []) or [])
            t_models = list(getattr(target_unit, "models", []) or [])
    except Exception:
        return False

    s_alive = [m for m in s_models if getattr(m, "is_alive", True)]
    t_alive = [m for m in t_models if getattr(m, "is_alive", True)]
    if not s_alive or not t_alive:
        return False

    # Short-circuit on first match
    for sm in s_alive:
        for tm in t_alive:
            if distance_between_models_bases_3d(sm, tm) <= r + 1e-6:
                return True
    return False


def model_wholly_within_range_of_unit(
    source_unit,
    target_model,
    radius: float,
    *,
    use_attached_aggregate: bool = True,
) -> bool:
    """
    A model is wholly within X of a unit if every point of its base/hull is within X (3D)
    of the source unit.

    Because bases/hulls are planar at model_base.z, the 3D condition reduces to:
      dxy <= sqrt(X^2 - dz^2) for some source model, where dz = abs(z_target - z_source).

    We implement this exactly in 2D using per-source-model buffered polygons and `covers()`.
    """
    try:
        r = float(radius)
    except Exception:
        return False
    if r < 0:
        return False

    target_shape = _base_shape(target_model)
    if target_shape is None:
        return False

    try:
        tz = float(getattr(getattr(target_model, "model_base", None), "z", 0.0))
    except Exception:
        tz = 0.0

    try:
        if use_attached_aggregate:
            s_models = source_unit.get_attached_unit_models()
        else:
            s_models = list(getattr(source_unit, "models", []) or [])
    except Exception:
        return False

    buffers = []
    for sm in [m for m in s_models if getattr(m, "is_alive", True)]:
        s_shape = _base_shape(sm)
        if s_shape is None:
            continue
        try:
            sz = float(getattr(getattr(sm, "model_base", None), "z", 0.0))
        except Exception:
            sz = 0.0
        dz = abs(tz - sz)
        if dz > r + 1e-6:
            continue
        # allowable 2D radius given vertical separation
        r2 = math.sqrt(max(0.0, (r * r) - (dz * dz)))
        try:
            buffers.append(s_shape.buffer(r2))
        except Exception:
            continue

    if not buffers:
        return False

    try:
        cover = unary_union(buffers)
        return bool(cover.covers(target_shape))
    except Exception:
        return False


def unit_wholly_within_range_of_unit(
    source_unit,
    target_unit,
    radius: float,
    *,
    use_attached_aggregate: bool = True,
) -> bool:
    """A unit is wholly within X if ALL its alive models are wholly within X."""
    try:
        if use_attached_aggregate:
            t_models = target_unit.get_attached_unit_models()
        else:
            t_models = list(getattr(target_unit, "models", []) or [])
    except Exception:
        return False

    alive = [m for m in t_models if getattr(m, "is_alive", True)]
    if not alive:
        return False
    for tm in alive:
        if not model_wholly_within_range_of_unit(source_unit, tm, radius, use_attached_aggregate=use_attached_aggregate):
            return False
    return True


# ---------------------------------------------------------------------------
# Point distance helpers (for mission cards like "within X\" of the centre")
# ---------------------------------------------------------------------------

def horizontal_distance_point_to_base_2d(base, x: float, y: float) -> float:
    """2D edge distance from a point to a base/hull shape (0 if point is inside)."""
    if base is None:
        return float("inf")
    try:
        px = float(x)
        py = float(y)
    except Exception:
        return float("inf")
    try:
        shape = base.get_base_shape()
        return float(shape.distance(ShapelyPoint(px, py)))
    except Exception:
        return float("inf")


def horizontal_distance_point_to_model_base_2d(model, x: float, y: float) -> float:
    """Convenience wrapper around horizontal_distance_point_to_base_2d for a Model-like object."""
    if model is None:
        return float("inf")
    base = getattr(model, "model_base", None)
    return horizontal_distance_point_to_base_2d(base, x, y)


def unit_within_horizontal_distance_of_point(unit, x: float, y: float, radius: float) -> bool:
    """
    A unit is within X\" of a point if ANY alive model's base/hull is within X\" (2D) of that point.
    Uses base edge distance (i.e., consistent with base-to-point measurements).
    """
    try:
        r = float(radius)
    except Exception:
        return False
    if r < 0:
        return False
    models = list(getattr(unit, "models", []) or [])
    for m in models:
        if not getattr(m, "is_alive", True):
            continue
        if horizontal_distance_point_to_model_base_2d(m, x, y) <= r + 1e-6:
            return True
    return False

