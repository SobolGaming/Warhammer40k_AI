from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional
from shapely.errors import GEOSException
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from ..utility.entity_ids import maybe_entity_id


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _round6(value: float) -> float:
    return float(round(float(value), 6))


def _zone_bounds(zone: dict | None, *, board_width: float, board_height: float) -> tuple[float, float, float, float]:
    zone_data = dict(zone or {})
    mission_zones = list(zone_data.get("mission_zones", []) or [])
    xs: list[float] = []
    ys: list[float] = []
    for mission_zone in mission_zones:
        for vertex in list(getattr(mission_zone, "vertices", []) or []):
            if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
                continue
            xs.append(_safe_float(vertex[0]))
            ys.append(_safe_float(vertex[1]))
    if xs and ys:
        return (min(xs), max(xs), min(ys), max(ys))
    x_range = zone_data.get("x_range")
    y_range = zone_data.get("y_range")
    if isinstance(x_range, (list, tuple)) and isinstance(y_range, (list, tuple)) and len(x_range) >= 2 and len(y_range) >= 2:
        lo_x = _safe_float(min(x_range[0], x_range[1]), 0.0)
        hi_x = _safe_float(max(x_range[0], x_range[1]), board_width)
        lo_y = _safe_float(min(y_range[0], y_range[1]), 0.0)
        hi_y = _safe_float(max(y_range[0], y_range[1]), board_height)
        return (lo_x, hi_x, lo_y, hi_y)
    return (0.0, float(board_width), 0.0, float(board_height))


def _zone_center(zone: dict | None, *, board_width: float, board_height: float) -> tuple[float, float]:
    min_x, max_x, min_y, max_y = _zone_bounds(zone, board_width=board_width, board_height=board_height)
    return (float((min_x + max_x) * 0.5), float((min_y + max_y) * 0.5))


def _objective_entries(game: object) -> list[dict[str, Any]]:
    objectives = list(getattr(game, "objectives", []) or [])
    entries: list[dict[str, Any]] = []
    for objective in objectives:
        objective_id = str(getattr(objective, "id", "") or "")
        location = getattr(objective, "location", None)
        x = _safe_float(getattr(location, "x", None), 0.0)
        y = _safe_float(getattr(location, "y", None), 0.0)
        entries.append({"objective_id": objective_id, "x": x, "y": y})
    entries.sort(key=lambda entry: str(entry.get("objective_id", "")))
    return entries


def _distance2d(x1: float, y1: float, x2: float, y2: float) -> float:
    dx = float(x1) - float(x2)
    dy = float(y1) - float(y2)
    return float((dx * dx + dy * dy) ** 0.5)


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(float(low), min(float(high), float(value)))


def _terrain_type_name(feature: object) -> str:
    terrain_type_obj = getattr(feature, "terrain_type", None)
    return str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "").upper()


def _safe_union(geometries: list[object]):
    if not geometries:
        return None
    try:
        return unary_union(geometries)
    except GEOSException:
        return None


def _line_intersects(line: LineString, geometry: object | None) -> bool:
    if geometry is None:
        return False
    try:
        return bool(line.intersects(geometry))
    except GEOSException:
        return False


def _point_distance(point: Point, geometry: object | None) -> float:
    if geometry is None:
        return float("inf")
    try:
        return float(point.distance(geometry))
    except GEOSException:
        return float("inf")


def _line_blockage_count(line: LineString, blockers: list[object]) -> int:
    blocked = 0
    for blocker in blockers:
        try:
            if line.intersects(blocker):
                blocked += 1
        except GEOSException:
            continue
    return int(blocked)


def _route_blockage_count(points: list[tuple[float, float]], blockers: list[object]) -> int:
    if len(points) < 2:
        return 0
    total = 0
    for idx in range(len(points) - 1):
        segment = LineString([points[idx], points[idx + 1]])
        total += _line_blockage_count(segment, blockers)
    return int(total)


@dataclass(frozen=True)
class BoardAffordanceSummary:
    board_width: float
    board_height: float
    deployment_center_x: float
    deployment_center_y: float
    terrain_feature_count: int
    terrain_type_counts: dict[str, int]
    los_blocking_feature_count: int
    ruins_count: int
    hidden_staging_pockets: tuple[str, ...]
    safe_firing_pockets: tuple[str, ...]
    upper_floor_fire_nests: tuple[str, ...]
    breachable_melee_corridors: int
    opening_constrained_vehicle_corridors: int
    reserve_entry_lane_quality: dict[str, float]
    objective_lane_distances: tuple[dict[str, Any], ...]
    threat_lane_count: int
    hidden_staging_cell_count: int
    must_expose_to_advance_cell_count: int
    los_tunnel_count: int
    infantry_objective_approach_quality: float
    vehicle_objective_approach_quality: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_width": float(self.board_width),
            "board_height": float(self.board_height),
            "deployment_center_x": float(self.deployment_center_x),
            "deployment_center_y": float(self.deployment_center_y),
            "terrain_feature_count": int(self.terrain_feature_count),
            "terrain_type_counts": {
                str(key): int(value)
                for key, value in sorted((self.terrain_type_counts or {}).items())
            },
            "los_blocking_feature_count": int(self.los_blocking_feature_count),
            "ruins_count": int(self.ruins_count),
            "hidden_staging_pockets": list(self.hidden_staging_pockets),
            "safe_firing_pockets": list(self.safe_firing_pockets),
            "upper_floor_fire_nests": list(self.upper_floor_fire_nests),
            "breachable_melee_corridors": int(self.breachable_melee_corridors),
            "opening_constrained_vehicle_corridors": int(self.opening_constrained_vehicle_corridors),
            "reserve_entry_lane_quality": {
                str(key): float(value)
                for key, value in sorted((self.reserve_entry_lane_quality or {}).items())
            },
            "objective_lane_distances": [dict(entry or {}) for entry in list(self.objective_lane_distances or [])],
            "threat_lane_count": int(self.threat_lane_count),
            "hidden_staging_cell_count": int(self.hidden_staging_cell_count),
            "must_expose_to_advance_cell_count": int(self.must_expose_to_advance_cell_count),
            "los_tunnel_count": int(self.los_tunnel_count),
            "infantry_objective_approach_quality": float(self.infantry_objective_approach_quality),
            "vehicle_objective_approach_quality": float(self.vehicle_objective_approach_quality),
        }


def compute_board_affordance_summary(
    game: object,
    *,
    deployment_zone: Optional[dict] = None,
) -> BoardAffordanceSummary:
    game_map = getattr(game, "map", None)
    board_width = _safe_float(getattr(game_map, "width", 60.0), 60.0)
    board_height = _safe_float(getattr(game_map, "height", 44.0), 44.0)
    center_x, center_y = _zone_center(deployment_zone, board_width=board_width, board_height=board_height)
    terrain_features = list(getattr(game_map, "terrain_features", []) or [])
    terrain_feature_count = int(len(terrain_features))
    terrain_type_counts: dict[str, int] = {}

    hidden_staging: list[str] = []
    safe_firing: list[str] = []
    upper_floor_nests: list[str] = []
    breachable_corridors = 0
    opening_constrained_corridors = 0
    lane_cover_scores = {
        "north_edge": 0.0,
        "south_edge": 0.0,
        "west_edge": 0.0,
        "east_edge": 0.0,
    }
    threat_lane_count = 0
    ruins_count = 0
    los_tunnel_count = 0
    infantry_quality_scores: list[float] = []
    vehicle_quality_scores: list[float] = []
    blocker_shapes: list[object] = []
    cover_shapes: list[object] = []
    blocker_feature_ids: set[str] = set()
    opening_constrained_shapes: list[object] = []

    for idx, feature in enumerate(terrain_features):
        terrain_id = str(getattr(feature, "id", "") or f"terrain_{idx}")
        terrain_type = _terrain_type_name(feature)
        terrain_type_counts[terrain_type] = int(terrain_type_counts.get(terrain_type, 0)) + 1
        walls = list(getattr(feature, "walls", []) or [])
        openings = list(getattr(feature, "openings", []) or [])
        floors = list(getattr(feature, "floors", []) or [])
        opening_count = int(len(openings))
        wall_count = int(len(walls))
        floor_count = int(len(floors))
        footprint = getattr(feature, "footprint", None)
        if footprint is not None:
            cover_shapes.append(footprint)

        traversal_rules = dict(getattr(feature, "traversal_rules", {}) or {})
        blocks_los = bool(traversal_rules.get("blocks_line_of_sight", False))
        if terrain_type in {"RUINS", "BARRICADE_AND_FUEL_PIPES", "HILLS_AND_SEALED_BUILDINGS"}:
            blocks_los = True
        if blocks_los and footprint is not None:
            blocker_shapes.append(footprint)
            blocker_feature_ids.add(terrain_id)
        if terrain_type == "RUINS":
            ruins_count += 1
            if wall_count > 0 and opening_count <= max(1, wall_count // 4):
                hidden_staging.append(terrain_id)
            if floor_count > 1:
                upper_floor_nests.append(terrain_id)
            if opening_count >= 2:
                safe_firing.append(terrain_id)
            if wall_count > 0 and opening_count > 0:
                breachable_corridors += 1
            if wall_count > 0 and opening_count <= 1:
                opening_constrained_corridors += 1
                if footprint is not None:
                    opening_constrained_shapes.append(footprint)
        else:
            if blocks_los and footprint is not None:
                area = _safe_float(getattr(footprint, "area", 0.0), 0.0)
                if area >= 12.0:
                    hidden_staging.append(terrain_id)
                else:
                    safe_firing.append(terrain_id)
                if terrain_type in {"BARRICADE_AND_FUEL_PIPES"}:
                    opening_constrained_corridors += 1
                    opening_constrained_shapes.append(footprint)
                elif terrain_type in {"CRATER_AND_RUBBLE", "DEBRIS_AND_STATUARY", "WOODS"}:
                    breachable_corridors += 1

        if terrain_type in {"HILLS_AND_SEALED_BUILDINGS"}:
            upper_floor_nests.append(terrain_id)

        centroid = getattr(footprint, "centroid", None)
        centroid_x = _safe_float(getattr(centroid, "x", None), center_x)
        centroid_y = _safe_float(getattr(centroid, "y", None), center_y)
        north_bias = max(0.0, centroid_y / max(1.0, board_height))
        south_bias = max(0.0, 1.0 - north_bias)
        east_bias = max(0.0, centroid_x / max(1.0, board_width))
        west_bias = max(0.0, 1.0 - east_bias)
        lane_weight = 0.2 if blocks_los else 0.08
        lane_cover_scores["north_edge"] += north_bias * lane_weight
        lane_cover_scores["south_edge"] += south_bias * lane_weight
        lane_cover_scores["east_edge"] += east_bias * lane_weight
        lane_cover_scores["west_edge"] += west_bias * lane_weight

        if blocks_los and (opening_count <= 1 or terrain_type in {"BARRICADE_AND_FUEL_PIPES"}):
            threat_lane_count += 1

    blockers_union = _safe_union(blocker_shapes)
    cover_union = _safe_union(cover_shapes)
    min_x, max_x, min_y, max_y = _zone_bounds(
        deployment_zone,
        board_width=board_width,
        board_height=board_height,
    )
    sample_step = _clamp(min(board_width, board_height) / 12.0, low=2.5, high=4.5)
    hidden_staging_cell_count = 0
    must_expose_to_advance_cell_count = 0
    sx = min_x + sample_step * 0.5
    while sx <= max_x + 1e-6:
        sy = min_y + sample_step * 0.5
        while sy <= max_y + 1e-6:
            point = Point(float(sx), float(sy))
            near_cover = bool(cover_union is not None and _point_distance(point, cover_union) <= sample_step * 0.55)
            blocked_to_center = bool(
                blockers_union is not None
                and _line_intersects(LineString([(float(sx), float(sy)), (center_x, center_y)]), blockers_union)
            )
            if near_cover and blocked_to_center:
                hidden_staging_cell_count += 1
            if (not near_cover) and (not blocked_to_center):
                must_expose_to_advance_cell_count += 1
            sy += sample_step
        sx += sample_step

    objective_entries = _objective_entries(game)
    objective_lane_distances: list[dict[str, Any]] = []
    for entry in objective_entries:
        objective_id = str(entry.get("objective_id", "") or "")
        x = _safe_float(entry.get("x"), center_x)
        y = _safe_float(entry.get("y"), center_y)
        direct_distance = _distance2d(center_x, center_y, x, y)
        direct_line = LineString([(center_x, center_y), (x, y)])
        direct_blocked_count = _line_blockage_count(direct_line, blocker_shapes)
        dx = x - center_x
        dy = y - center_y
        mag = max(1e-6, float((dx * dx + dy * dy) ** 0.5))
        side_x = -dy / mag
        side_y = dx / mag
        route_offset = _clamp(direct_distance * 0.25, low=3.0, high=8.0)
        midpoint_x = (center_x + x) * 0.5
        midpoint_y = (center_y + y) * 0.5
        left_mid = (midpoint_x + side_x * route_offset, midpoint_y + side_y * route_offset)
        right_mid = (midpoint_x - side_x * route_offset, midpoint_y - side_y * route_offset)
        left_route_blocked = _route_blockage_count([(center_x, center_y), left_mid, (x, y)], blocker_shapes)
        right_route_blocked = _route_blockage_count([(center_x, center_y), right_mid, (x, y)], blocker_shapes)
        best_route_blocked = min(direct_blocked_count, left_route_blocked, right_route_blocked)
        infantry_quality = _clamp(
            1.0 - float(best_route_blocked) * 0.22 + (0.08 if direct_blocked_count > best_route_blocked else 0.0),
            low=0.0,
            high=1.0,
        )
        vehicle_quality = _clamp(
            infantry_quality - float(opening_constrained_corridors) * 0.02 - (0.05 if best_route_blocked > 0 else 0.0),
            low=0.0,
            high=1.0,
        )
        infantry_quality_scores.append(float(infantry_quality))
        vehicle_quality_scores.append(float(vehicle_quality))
        if direct_blocked_count > 0 and best_route_blocked <= max(1, direct_blocked_count - 1):
            los_tunnel_count += 1
        objective_lane_distances.append(
            {
                "objective_id": objective_id,
                "distance_from_deployment_center": _round6(direct_distance),
                "x": _round6(x),
                "y": _round6(y),
                "direct_lane_blockers": int(direct_blocked_count),
                "best_route_blockers": int(best_route_blocked),
                "infantry_approach_quality": _round6(infantry_quality),
                "vehicle_approach_quality": _round6(vehicle_quality),
            }
        )
    objective_lane_distances.sort(key=lambda entry: str(entry.get("objective_id", "")))
    infantry_objective_approach_quality = (
        float(sum(infantry_quality_scores) / float(len(infantry_quality_scores)))
        if infantry_quality_scores
        else 0.0
    )
    vehicle_objective_approach_quality = (
        float(sum(vehicle_quality_scores) / float(len(vehicle_quality_scores)))
        if vehicle_quality_scores
        else 0.0
    )
    lane_scale = float(max(1, len(blocker_feature_ids)))
    lane_bonus = infantry_objective_approach_quality * 0.18
    reserve_entry_lane_quality = {
        key: _round6(max(0.0, (float(value) / lane_scale) + lane_bonus))
        for key, value in sorted(lane_cover_scores.items())
    }
    hidden_staging.sort()
    safe_firing.sort()
    upper_floor_nests.sort()

    return BoardAffordanceSummary(
        board_width=float(board_width),
        board_height=float(board_height),
        deployment_center_x=float(center_x),
        deployment_center_y=float(center_y),
        terrain_feature_count=int(terrain_feature_count),
        terrain_type_counts={str(key): int(value) for key, value in sorted(terrain_type_counts.items())},
        los_blocking_feature_count=int(len(blocker_feature_ids)),
        ruins_count=int(ruins_count),
        hidden_staging_pockets=tuple(hidden_staging),
        safe_firing_pockets=tuple(safe_firing),
        upper_floor_fire_nests=tuple(upper_floor_nests),
        breachable_melee_corridors=int(breachable_corridors),
        opening_constrained_vehicle_corridors=int(opening_constrained_corridors),
        reserve_entry_lane_quality=reserve_entry_lane_quality,
        objective_lane_distances=tuple(objective_lane_distances),
        threat_lane_count=int(max(0, threat_lane_count)),
        hidden_staging_cell_count=int(hidden_staging_cell_count),
        must_expose_to_advance_cell_count=int(must_expose_to_advance_cell_count),
        los_tunnel_count=int(los_tunnel_count),
        infantry_objective_approach_quality=_round6(infantry_objective_approach_quality),
        vehicle_objective_approach_quality=_round6(vehicle_objective_approach_quality),
    )


def zone_area_frontage_depth(zone: dict | None, *, board_width: float, board_height: float) -> tuple[float, float, float]:
    min_x, max_x, min_y, max_y = _zone_bounds(zone, board_width=board_width, board_height=board_height)
    span_x = max(0.0, float(max_x) - float(min_x))
    span_y = max(0.0, float(max_y) - float(min_y))
    area = float(span_x * span_y)
    frontage = float(max(span_x, span_y))
    depth = float(min(span_x, span_y))
    mission_zones = list(dict(zone or {}).get("mission_zones", []) or [])
    if mission_zones:
        area = 0.0
        for mission_zone in mission_zones:
            vertices: list[tuple[float, float]] = []
            for vertex in list(getattr(mission_zone, "vertices", []) or []):
                if not isinstance(vertex, (list, tuple)) or len(vertex) < 2:
                    continue
                vertices.append((_safe_float(vertex[0]), _safe_float(vertex[1])))
            if len(vertices) < 3:
                continue
            partial = 0.0
            for idx, current in enumerate(vertices):
                nxt = vertices[(idx + 1) % len(vertices)]
                partial += float(current[0]) * float(nxt[1]) - float(nxt[0]) * float(current[1])
            area += abs(partial) * 0.5
    return (_round6(area), _round6(frontage), _round6(depth))


def deployment_zone_from_player(game: object, player_id: str) -> Optional[dict]:
    zones = dict(getattr(game, "deployment_zones", {}) or {})
    entry = zones.get(player_id)
    if isinstance(entry, dict):
        return dict(entry)
    return None


def sorted_units(units: Iterable[object]) -> list[object]:
    entries: list[tuple[str, object]] = []
    for unit in list(units or []):
        unit_id = str(maybe_entity_id(unit) or "")
        if not unit_id:
            continue
        entries.append((unit_id, unit))
    entries.sort(key=lambda entry: entry[0])
    return [entry[1] for entry in entries]
