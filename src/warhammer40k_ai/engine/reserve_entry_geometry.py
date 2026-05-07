from __future__ import annotations

from typing import Any

from ..utility.call_utils import call_with_supported_kwargs
from ..utility.entity_ids import get_entity_id

_STRATEGIC_RESERVES_EDGES = ("own", "left", "right", "enemy")
_BATTLEFIELD_EDGE_NORMALS = {
    "own": (0.0, -1.0),
    "enemy": (0.0, 1.0),
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
}
_EDGE_CONTACT_EPSILON = 1e-6
_ENEMY_EDGE_SCORE_RATIO = 0.25


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


def _unit_owner_player_id(unit: object | None) -> str:
    if unit is None:
        return ""
    get_parent_army = getattr(unit, "get_parent_army", None)
    army = get_parent_army() if callable(get_parent_army) else getattr(unit, "army", None)
    player = getattr(army, "player", None)
    player_id = getattr(player, "id", None)
    return str(player_id or "").strip()


def _current_player_id(game: object) -> str:
    get_current_player = getattr(game, "get_current_player", None)
    player = get_current_player() if callable(get_current_player) else None
    player_id = getattr(player, "id", None)
    return str(player_id or "").strip()


def _battlefield_edge_line(edge: str, *, width: float, height: float):
    from shapely.geometry import LineString

    if edge == "own":
        return LineString([(0.0, 0.0), (float(width), 0.0)])
    if edge == "enemy":
        return LineString([(0.0, float(height)), (float(width), float(height))])
    if edge == "left":
        return LineString([(0.0, 0.0), (0.0, float(height))])
    if edge == "right":
        return LineString([(float(width), 0.0), (float(width), float(height))])
    return None


def _deployment_zone_geometry(mission_zone: object):
    from shapely.geometry import Polygon

    vertices = list(getattr(mission_zone, "vertices", []) or [])
    if len(vertices) < 3:
        return None
    zone_geometry = Polygon(vertices)
    if not bool(getattr(zone_geometry, "is_valid", True)):
        zone_geometry = zone_geometry.buffer(0)
    if bool(getattr(zone_geometry, "is_empty", False)):
        return None
    for cutout in list(getattr(mission_zone, "cutouts", []) or []):
        get_cutout_geometry = getattr(cutout, "get_shapely_geometry", None)
        if not callable(get_cutout_geometry):
            continue
        cutout_geometry = get_cutout_geometry()
        if cutout_geometry is None or bool(getattr(cutout_geometry, "is_empty", False)):
            continue
        if not bool(getattr(cutout_geometry, "is_valid", True)):
            cutout_geometry = cutout_geometry.buffer(0)
        zone_geometry = zone_geometry.difference(cutout_geometry)
        if bool(getattr(zone_geometry, "is_empty", False)):
            return None
    return zone_geometry


def _deployment_geometries_for_owner(game: object, player_id: str, *, opponents: bool) -> list[object]:
    owner_id = str(player_id or "").strip()
    if not owner_id:
        return []
    zones = getattr(game, "deployment_zones", None)
    if not isinstance(zones, dict) or not zones:
        return []

    geometries: list[object] = []
    for zone_player_id, zone_info in zones.items():
        zone_owner_id = str(zone_player_id or "").strip()
        if opponents and zone_owner_id == owner_id:
            continue
        if not opponents and zone_owner_id != owner_id:
            continue
        mission_zones = list((zone_info or {}).get("mission_zones", []) or []) if isinstance(zone_info, dict) else []
        for mission_zone in mission_zones:
            zone_geometry = _deployment_zone_geometry(mission_zone)
            if zone_geometry is not None:
                geometries.append(zone_geometry)
    return geometries


def _union_deployment_geometries(geometries: list[object]):
    if not geometries:
        return None
    from shapely.ops import unary_union

    union = unary_union(geometries)
    if union is None or bool(getattr(union, "is_empty", False)):
        return None
    if not bool(getattr(union, "is_valid", True)):
        union = union.buffer(0)
    if bool(getattr(union, "is_empty", False)):
        return None
    return union


def _deployment_edge_contact_lengths(geometry: object, *, width: float, height: float) -> dict[str, float]:
    contact_lengths: dict[str, float] = {edge: 0.0 for edge in _STRATEGIC_RESERVES_EDGES}
    boundary = getattr(geometry, "boundary", None)
    if boundary is None:
        return contact_lengths
    for edge in _STRATEGIC_RESERVES_EDGES:
        edge_line = _battlefield_edge_line(edge, width=float(width), height=float(height))
        if edge_line is None:
            continue
        contact = boundary.intersection(edge_line)
        contact_lengths[str(edge)] += float(getattr(contact, "length", 0.0) or 0.0)
    return contact_lengths


def _fallback_contact_edges(contact_lengths: dict[str, float]) -> tuple[str, ...]:
    max_contact = max(contact_lengths.values(), default=0.0)
    if max_contact <= _EDGE_CONTACT_EPSILON:
        return tuple()
    return tuple(
        edge
        for edge in _STRATEGIC_RESERVES_EDGES
        if contact_lengths.get(edge, 0.0) >= max_contact - _EDGE_CONTACT_EPSILON
    )


def enemy_deployment_battlefield_edges(game: object, player_id: str) -> tuple[str, ...]:
    """Infer the opponent battlefield edge(s) from mission deployment-zone geometry."""
    owner_id = str(player_id or "").strip()
    if not owner_id:
        return tuple()
    width, height = battlefield_dimensions(game)
    if width is None or height is None:
        return tuple()

    own_geometry = _union_deployment_geometries(
        _deployment_geometries_for_owner(game, owner_id, opponents=False)
    )
    opponent_geometry = _union_deployment_geometries(
        _deployment_geometries_for_owner(game, owner_id, opponents=True)
    )
    if opponent_geometry is None:
        return tuple()

    contact_lengths = _deployment_edge_contact_lengths(
        opponent_geometry,
        width=float(width),
        height=float(height),
    )
    if own_geometry is None:
        return _fallback_contact_edges(contact_lengths)

    own_centroid = own_geometry.centroid
    opponent_centroid = opponent_geometry.centroid
    delta_x = float(opponent_centroid.x) - float(own_centroid.x)
    delta_y = float(opponent_centroid.y) - float(own_centroid.y)
    magnitude = (delta_x * delta_x + delta_y * delta_y) ** 0.5
    if magnitude <= _EDGE_CONTACT_EPSILON:
        return _fallback_contact_edges(contact_lengths)

    unit_x = delta_x / magnitude
    unit_y = delta_y / magnitude
    edge_scores: dict[str, float] = {}
    for edge in _STRATEGIC_RESERVES_EDGES:
        contact_length = float(contact_lengths.get(edge, 0.0) or 0.0)
        if contact_length <= _EDGE_CONTACT_EPSILON:
            continue
        normal_x, normal_y = _BATTLEFIELD_EDGE_NORMALS[edge]
        direction_score = max(0.0, unit_x * normal_x + unit_y * normal_y)
        if direction_score <= _EDGE_CONTACT_EPSILON:
            continue
        edge_scores[edge] = contact_length * direction_score

    max_score = max(edge_scores.values(), default=0.0)
    if max_score <= _EDGE_CONTACT_EPSILON:
        return _fallback_contact_edges(contact_lengths)
    return tuple(
        edge
        for edge in _STRATEGIC_RESERVES_EDGES
        if edge_scores.get(edge, 0.0) >= max_score * _ENEMY_EDGE_SCORE_RATIO - _EDGE_CONTACT_EPSILON
    )


def is_valid_strategic_reserves_edge(
    game: object,
    battlefield_edge: str,
    *,
    turn: int | None = None,
    player_id: str | None = None,
    unit: object | None = None,
) -> bool:
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
        battle_round = int(use_turn or 0)
    except (TypeError, ValueError):
        return False
    if battle_round < 2:
        return False
    if battle_round >= 3:
        return True

    owner_id = str(player_id or "").strip() or _unit_owner_player_id(unit) or _current_player_id(game)
    invalid_edges = set(enemy_deployment_battlefield_edges(game, owner_id))
    if invalid_edges:
        return edge not in invalid_edges
    return True


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
