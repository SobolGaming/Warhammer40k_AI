from __future__ import annotations

from typing import Any

from ..utility.call_utils import call_with_supported_kwargs
from ..utility.entity_ids import get_entity_id

_STRATEGIC_RESERVES_EDGES = ("own", "left", "right", "enemy")


def battlefield_dimensions(game: object) -> tuple[float | None, float | None]:
    battlefield = getattr(game, "battlefield", None)
    if battlefield is not None:
        try:
            return (float(getattr(battlefield, "width", None)), float(getattr(battlefield, "height", None)))
        except (TypeError, ValueError):
            pass
    game_map = getattr(game, "map", None)
    if game_map is not None:
        try:
            return (float(getattr(game_map, "width", None)), float(getattr(game_map, "height", None)))
        except (TypeError, ValueError):
            pass
    return (None, None)


def strategic_reserves_edges() -> tuple[str, ...]:
    return _STRATEGIC_RESERVES_EDGES


def is_valid_strategic_reserves_edge(game: object, battlefield_edge: str, *, turn: int | None = None) -> bool:
    edge = str(battlefield_edge or "").strip().lower()
    if edge not in _STRATEGIC_RESERVES_EDGES:
        return False
    use_turn = getattr(game, "turn", 0)
    if turn is not None:
        try:
            use_turn = int(turn)
        except (TypeError, ValueError):
            use_turn = getattr(game, "turn", 0)
    try:
        return int(use_turn or 0) >= 2
    except (TypeError, ValueError):
        return False


def distance_to_battlefield_edge(
    position: tuple[float, float, float] | tuple[float, float],
    battlefield_edge: str,
    *,
    game: object | None = None,
    width: float | None = None,
    height: float | None = None,
) -> float:
    use_width = width
    use_height = height
    if (use_width is None or use_height is None) and game is not None:
        use_width, use_height = battlefield_dimensions(game)
    if use_width is None or use_height is None:
        return float("inf")
    x = float(position[0])
    y = float(position[1])
    edge = str(battlefield_edge or "").strip().lower()
    if edge == "own":
        return float(y)
    if edge == "enemy":
        return float(use_height - y)
    if edge == "left":
        return float(x)
    if edge == "right":
        return float(use_width - x)
    return float("inf")


def model_radius(model: object) -> float:
    base = getattr(model, "model_base", None)
    if base is None:
        return 1.0
    get_longest_radius = getattr(base, "get_longest_radius", None)
    if callable(get_longest_radius):
        return float(get_longest_radius())
    get_radius = getattr(base, "get_radius", None)
    if callable(get_radius):
        return float(get_radius())
    radius = getattr(base, "radius", None)
    if isinstance(radius, (list, tuple)) and radius:
        return float(radius[0])
    if radius is not None:
        return float(radius)
    return 1.0


def model_footprint_bounds_at(
    unit: object,
    model: object,
    *,
    x: float,
    y: float,
    z: float,
    facing: float,
) -> tuple[float, float, float, float] | None:
    create_base = getattr(unit, "_create_potential_base", None)
    if callable(create_base):
        try:
            candidate_base = create_base(float(x), float(y), float(z), float(facing), model=model)
        except (AttributeError, TypeError, ValueError):
            candidate_base = None
        if candidate_base is not None:
            get_shape = getattr(candidate_base, "get_base_shape", None)
            if callable(get_shape):
                shape = get_shape()
                if shape is not None and not bool(getattr(shape, "is_empty", False)):
                    min_x, min_y, max_x, max_y = shape.bounds
                    return (float(min_x), float(min_y), float(max_x), float(max_y))

    base = getattr(model, "model_base", None)
    get_shape_at = getattr(base, "get_base_shape_at", None)
    if callable(get_shape_at):
        shape = get_shape_at(float(x), float(y), float(facing))
        if shape is not None and not bool(getattr(shape, "is_empty", False)):
            min_x, min_y, max_x, max_y = shape.bounds
            return (float(min_x), float(min_y), float(max_x), float(max_y))
    return None


def strategic_edge_footprint_metrics(
    unit: object,
    model: object,
    *,
    x: float,
    y: float,
    z: float,
    facing: float,
    battlefield_edge: str,
    width: float,
    height: float,
    touch_tolerance: float = 0.25,
) -> dict[str, float | bool] | None:
    bounds = model_footprint_bounds_at(unit, model, x=float(x), y=float(y), z=float(z), facing=float(facing))
    if bounds is None:
        return None

    min_x, min_y, max_x, max_y = bounds
    edge = str(battlefield_edge or "").strip().lower()
    if edge == "own":
        near_gap = float(min_y)
        far_distance = float(max_y)
        center_distance = float(y)
        toward_edge_extent = float(y) - float(min_y)
        away_edge_extent = float(max_y) - float(y)
        perpendicular_extent = float(max_y) - float(min_y)
    elif edge == "enemy":
        near_gap = float(height) - float(max_y)
        far_distance = float(height) - float(min_y)
        center_distance = float(height) - float(y)
        toward_edge_extent = float(max_y) - float(y)
        away_edge_extent = float(y) - float(min_y)
        perpendicular_extent = float(max_y) - float(min_y)
    elif edge == "left":
        near_gap = float(min_x)
        far_distance = float(max_x)
        center_distance = float(x)
        toward_edge_extent = float(x) - float(min_x)
        away_edge_extent = float(max_x) - float(x)
        perpendicular_extent = float(max_x) - float(min_x)
    elif edge == "right":
        near_gap = float(width) - float(max_x)
        far_distance = float(width) - float(min_x)
        center_distance = float(width) - float(x)
        toward_edge_extent = float(max_x) - float(x)
        away_edge_extent = float(x) - float(min_x)
        perpendicular_extent = float(max_x) - float(min_x)
    else:
        return None

    overhang_epsilon = 1e-6
    overhangs_board = bool(
        min_x < -overhang_epsilon
        or min_y < -overhang_epsilon
        or max_x > float(width) + overhang_epsilon
        or max_y > float(height) + overhang_epsilon
    )
    within_six = bool(near_gap >= -overhang_epsilon and far_distance <= 6.0 + overhang_epsilon)
    requires_edge_touch = bool(float(perpendicular_extent) > 6.0 + overhang_epsilon)
    touches_edge = bool(near_gap >= -overhang_epsilon and near_gap <= float(touch_tolerance) + overhang_epsilon)
    return {
        "min_x": float(min_x),
        "min_y": float(min_y),
        "max_x": float(max_x),
        "max_y": float(max_y),
        "near_gap": float(near_gap),
        "far_distance": float(far_distance),
        "center_distance": float(center_distance),
        "toward_edge_extent": float(toward_edge_extent),
        "away_edge_extent": float(away_edge_extent),
        "perpendicular_extent": float(perpendicular_extent),
        "overhangs_board": bool(overhangs_board),
        "within_six": bool(within_six),
        "requires_edge_touch": bool(requires_edge_touch),
        "touches_edge": bool(touches_edge),
    }


def strategic_edge_touch_offset_for_model(
    unit: object,
    model: object,
    *,
    battlefield_edge: str,
    facing: float,
) -> float | None:
    bounds = model_footprint_bounds_at(unit, model, x=0.0, y=0.0, z=0.0, facing=float(facing))
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    edge = str(battlefield_edge or "").strip().lower()
    if edge == "own":
        return float(max(0.0, -float(min_y)))
    if edge == "enemy":
        return float(max(0.0, float(max_y)))
    if edge == "left":
        return float(max(0.0, -float(min_x)))
    if edge == "right":
        return float(max(0.0, float(max_x)))
    return None


def prospective_positions_from_model_payload(unit: object, model_positions: object) -> dict[str, Any]:
    if not isinstance(model_positions, list) or not model_positions:
        return {"error": "Reserves arrival requires model positions."}

    positions_by_id: dict[str, tuple[float, float, float, float]] = {}
    for entry in list(model_positions or []):
        model_id = str(entry.get("model_id", "") or "")
        if not model_id:
            return {"error": "Reserves arrival missing model_id."}
        position = entry.get("position") or []
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            return {"error": "Reserves arrival missing position coordinates."}
        try:
            x = float(position[0])
            y = float(position[1])
            z = float(position[2]) if len(position) > 2 else 0.0
        except (TypeError, ValueError):
            return {"error": "Reserves arrival position coordinates must be numeric."}
        try:
            facing = float(entry.get("facing", 0.0) or 0.0)
        except (TypeError, ValueError):
            facing = 0.0
        positions_by_id[model_id] = (x, y, z, facing)

    prospective: list[tuple[float, float, float, float]] = []
    for model in list(getattr(unit, "models", []) or []):
        model_id = str(get_entity_id(model) or "")
        if model_id not in positions_by_id:
            return {"error": "Reserves arrival missing positions for all models."}
        prospective.append(positions_by_id[model_id])
    return {"prospective": prospective}


def build_model_positions_from_anchor(
    game: object,
    unit: object,
    *,
    x: float,
    y: float,
    avoid_friendly_units: bool,
    search_context: object | None = None,
) -> list[dict]:
    game_map = getattr(game, "map", None)
    if game_map is None or unit is None:
        return []
    boundary_repulsors = None
    repulsor_fn = getattr(game, "get_boundary_repulsors", None)
    if callable(repulsor_fn):
        boundary_repulsors = repulsor_fn(unit, context="reserves_arrival")
    elif hasattr(game_map, "get_battlefield_edge_repulsors"):
        boundary_repulsors = game_map.get_battlefield_edge_repulsors()
    model_positions = call_with_supported_kwargs(
        unit.calculate_model_positions,
        float(x),
        float(y),
        game_map,
        avoid_friendly_units=bool(avoid_friendly_units),
        boundary_repulsors=boundary_repulsors,
        search_context=search_context,
    )
    models = list(getattr(unit, "models", []) or [])
    if not model_positions or len(model_positions) != len(models):
        return []
    payload: list[dict] = []
    for model, position in zip(models, model_positions):
        model_id = str(get_entity_id(model) or "")
        if not model_id:
            return []
        px, py, pz, facing = position
        payload.append(
            {
                "model_id": model_id,
                "position": [float(px), float(py), float(pz)],
                "facing": float(facing),
            }
        )
    return payload
