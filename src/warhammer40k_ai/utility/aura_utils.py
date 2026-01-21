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


def unit_within_range_of_point_3d(
    unit,
    point: tuple[float, float],
    radius: float,
    *,
    use_attached_aggregate: bool = True,
) -> bool:
    """
    Check if a unit is within a given radius of a point (3D distance).

    Per AGENTS.md: distances are 3D unless explicitly stated as horizontal/vertical.

    Args:
        unit: The unit to check
        point: (x, y) coordinates of the point
        radius: Maximum distance in inches
        use_attached_aggregate: Whether to include attached units

    Returns:
        True if ANY model in the unit is within radius of the point
    """
    try:
        r = float(radius)
        px, py = float(point[0]), float(point[1])
    except Exception:
        return False
    if r < 0:
        return False

    try:
        if use_attached_aggregate:
            models = unit.get_attached_unit_models()
        else:
            models = list(getattr(unit, "models", []) or [])
    except Exception:
        return False

    alive_models = [m for m in models if getattr(m, "is_alive", True)]
    if not alive_models:
        return False

    # Check if any model is within radius of the point (edge-to-point distance)
    for model in alive_models:
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        dxy = float(horizontal_distance_point_to_base_2d(base, px, py))
        if math.isinf(dxy):
            continue
        dz = abs(float(getattr(base, "z", 0.0)))
        dist_3d = float(math.hypot(dxy, dz))
        if dist_3d <= r:
            return True

    return False


def get_units_within_range_of_point_3d(
    point: tuple[float, float],
    radius: float,
    all_units: Iterable,
    *,
    use_attached_aggregate: bool = True,
) -> list:
    """
    Get all units within a given radius of a point (3D distance).

    Per AGENTS.md: distances are 3D unless explicitly stated as horizontal/vertical.

    Args:
        point: (x, y) coordinates of the point
        radius: Maximum distance in inches
        all_units: Iterable of units to check
        use_attached_aggregate: Whether to include attached units

    Returns:
        List of units within radius of the point
    """
    units_in_range = []
    for unit in all_units:
        if unit_within_range_of_point_3d(unit, point, radius, use_attached_aggregate=use_attached_aggregate):
            units_in_range.append(unit)
    return units_in_range


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


def get_eligible_linked_fire_origin_units(bearer_unit, *, game_map=None):
    """
    Find eligible Fire Prism units for Linked Fire origin selection.

    Per Linked Fire rule: "you can measure range and determine visibility from another
    friendly FIRE PRISM model that is visible to the bearer."

    Returns list of units that are:
    - Friendly (same army as bearer)
    - Alive and deployed
    - Have FIRE PRISM keywords
    - Not the bearer unit itself
    - Visible to the bearer (at least one model of origin visible to at least one model of bearer)

    Args:
        bearer_unit: The unit with the Linked Fire weapon
        game_map: Optional game map for visibility checks

    Returns:
        List of eligible Fire Prism units
    """
    if bearer_unit is None or game_map is None:
        return []

    # Get all friendly units
    try:
        friendly_units = list(game_map.get_friendly_units(bearer_unit))
    except Exception:
        return []

    eligible = []
    for unit in friendly_units:
        if _is_linked_fire_origin_eligible(bearer_unit, unit, game_map=game_map):
            eligible.append(unit)

    return eligible


def _unit_is_alive(unit) -> bool:
    if unit is None:
        return False
    alive = getattr(unit, "is_alive", None)
    if callable(alive):
        return bool(alive())
    return bool(alive)


def _model_is_alive(model) -> bool:
    alive = getattr(model, "is_alive", True)
    if callable(alive):
        return bool(alive())
    return bool(alive)


def unit_has_fire_prism_keyword(unit) -> bool:
    if unit is None:
        return False
    try:
        if unit.has_any_keyword("Fire Prism"):
            return True
    except AttributeError:
        pass
    keywords = []
    try:
        keywords = list(getattr(unit, "get_effective_keywords")() or [])
    except AttributeError:
        keywords = list(getattr(unit, "keywords", []) or [])
    keyword_set = {str(k or "").strip().lower() for k in keywords if str(k or "").strip()}
    if "fire prism" in keyword_set:
        return True
    return "fire" in keyword_set and "prism" in keyword_set


def linked_fire_origin_is_visible(bearer_unit, origin_unit, *, game_map=None) -> bool:
    if bearer_unit is None or origin_unit is None or game_map is None:
        return False
    can_see_fn = getattr(game_map, "can_model_see_model", None)
    if not callable(can_see_fn):
        return False
    bearer_models = [m for m in (getattr(bearer_unit, "models", []) or []) if _model_is_alive(m)]
    origin_models = [m for m in (getattr(origin_unit, "models", []) or []) if _model_is_alive(m)]
    if not bearer_models or not origin_models:
        return False
    for bearer_model in bearer_models:
        for origin_model in origin_models:
            if can_see_fn(bearer_model, origin_model):
                return True
    return False


def _is_linked_fire_origin_eligible(bearer_unit, origin_unit, *, game_map=None) -> bool:
    if bearer_unit is None or origin_unit is None or game_map is None:
        return False
    try:
        from .entity_ids import get_entity_id
        if get_entity_id(origin_unit) == get_entity_id(bearer_unit):
            return False
    except ValueError:
        if origin_unit is bearer_unit:
            return False
    if not _unit_is_alive(origin_unit):
        return False
    if not bool(getattr(origin_unit, "deployed", False)):
        return False
    if not unit_has_fire_prism_keyword(origin_unit):
        return False
    return linked_fire_origin_is_visible(bearer_unit, origin_unit, game_map=game_map)
