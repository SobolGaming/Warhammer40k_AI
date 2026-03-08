from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional

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


@dataclass(frozen=True)
class BoardAffordanceSummary:
    board_width: float
    board_height: float
    deployment_center_x: float
    deployment_center_y: float
    ruins_count: int
    hidden_staging_pockets: tuple[str, ...]
    safe_firing_pockets: tuple[str, ...]
    upper_floor_fire_nests: tuple[str, ...]
    breachable_melee_corridors: int
    opening_constrained_vehicle_corridors: int
    reserve_entry_lane_quality: dict[str, float]
    objective_lane_distances: tuple[dict[str, Any], ...]
    threat_lane_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_width": float(self.board_width),
            "board_height": float(self.board_height),
            "deployment_center_x": float(self.deployment_center_x),
            "deployment_center_y": float(self.deployment_center_y),
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

    for idx, feature in enumerate(terrain_features):
        terrain_id = str(getattr(feature, "id", "") or f"terrain_{idx}")
        terrain_type_obj = getattr(feature, "terrain_type", None)
        terrain_type = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "").upper()
        if terrain_type != "RUINS":
            continue
        ruins_count += 1
        walls = list(getattr(feature, "walls", []) or [])
        openings = list(getattr(feature, "openings", []) or [])
        floors = list(getattr(feature, "floors", []) or [])
        opening_count = int(len(openings))
        wall_count = int(len(walls))
        floor_count = int(len(floors))
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

        footprint = getattr(feature, "footprint", None)
        centroid = getattr(footprint, "centroid", None)
        centroid_x = _safe_float(getattr(centroid, "x", None), center_x)
        centroid_y = _safe_float(getattr(centroid, "y", None), center_y)
        north_bias = max(0.0, centroid_y / max(1.0, board_height))
        south_bias = max(0.0, 1.0 - north_bias)
        east_bias = max(0.0, centroid_x / max(1.0, board_width))
        west_bias = max(0.0, 1.0 - east_bias)
        lane_cover_scores["north_edge"] += north_bias * 0.2
        lane_cover_scores["south_edge"] += south_bias * 0.2
        lane_cover_scores["east_edge"] += east_bias * 0.2
        lane_cover_scores["west_edge"] += west_bias * 0.2

        if opening_count <= 1 and floor_count >= 1:
            threat_lane_count += 1

    objective_entries = _objective_entries(game)
    objective_lane_distances: list[dict[str, Any]] = []
    for entry in objective_entries:
        objective_id = str(entry.get("objective_id", "") or "")
        x = _safe_float(entry.get("x"), center_x)
        y = _safe_float(entry.get("y"), center_y)
        objective_lane_distances.append(
            {
                "objective_id": objective_id,
                "distance_from_deployment_center": _round6(_distance2d(center_x, center_y, x, y)),
                "x": _round6(x),
                "y": _round6(y),
            }
        )
    objective_lane_distances.sort(key=lambda entry: str(entry.get("objective_id", "")))
    hidden_staging.sort()
    safe_firing.sort()
    upper_floor_nests.sort()

    return BoardAffordanceSummary(
        board_width=float(board_width),
        board_height=float(board_height),
        deployment_center_x=float(center_x),
        deployment_center_y=float(center_y),
        ruins_count=int(ruins_count),
        hidden_staging_pockets=tuple(hidden_staging),
        safe_firing_pockets=tuple(safe_firing),
        upper_floor_fire_nests=tuple(upper_floor_nests),
        breachable_melee_corridors=int(breachable_corridors),
        opening_constrained_vehicle_corridors=int(opening_constrained_corridors),
        reserve_entry_lane_quality={
            key: _round6(value)
            for key, value in sorted(lane_cover_scores.items())
        },
        objective_lane_distances=tuple(objective_lane_distances),
        threat_lane_count=int(threat_lane_count),
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
