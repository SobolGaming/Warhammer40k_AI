from __future__ import annotations

from typing import Any

from ..utility.constants import ENGAGEMENT_RANGE_HORIZONTAL, ENGAGEMENT_RANGE_VERTICAL
from ..utility.entity_ids import get_entity_id

STATE_BLOB_VERSION = "1.0.0"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        items = [_json_safe(v) for v in value]
        return sorted(items, key=lambda item: str(item))
    return str(value)


def _phase_name(game: object) -> str:
    phase = getattr(game, "phase", None)
    name = getattr(phase, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(phase or "")


def _battle_round(game: object) -> int:
    getter = getattr(game, "get_battle_round", None)
    if callable(getter):
        return _safe_int(getter(), 0)
    return _safe_int(getattr(game, "turn", 0), 0)


def _current_player_id(game: object) -> str:
    getter = getattr(game, "get_current_player", None)
    if not callable(getter):
        return ""
    player = getter()
    return str(getattr(player, "id", "") or "")


def _sorted_players(game: object) -> list[object]:
    players = list(getattr(game, "players", []) or [])
    return sorted(players, key=lambda player: str(getattr(player, "id", "") or ""))


def _alive_models(unit: object) -> list[object]:
    models = list(getattr(unit, "models", []) or [])
    alive: list[object] = []
    for model in models:
        is_alive_value = getattr(model, "is_alive", True)
        alive_flag = bool(is_alive_value() if callable(is_alive_value) else is_alive_value)
        if alive_flag:
            alive.append(model)
    return alive


def _model_position(model: object) -> tuple[float, float, float]:
    getter = getattr(model, "get_location", None)
    if callable(getter):
        location = getter()
        if isinstance(location, (list, tuple)) and len(location) >= 3:
            return (_safe_float(location[0]), _safe_float(location[1]), _safe_float(location[2]))
    base = getattr(model, "model_base", None)
    return (
        _safe_float(getattr(base, "x", 0.0), 0.0),
        _safe_float(getattr(base, "y", 0.0), 0.0),
        _safe_float(getattr(base, "z", 0.0), 0.0),
    )


def _unit_centroid(unit: object) -> tuple[float, float, float]:
    models = _alive_models(unit)
    if not models:
        position = getattr(unit, "position", None)
        if isinstance(position, (list, tuple)) and len(position) >= 3:
            return (_safe_float(position[0]), _safe_float(position[1]), _safe_float(position[2]))
        if isinstance(position, (list, tuple)) and len(position) >= 2:
            return (_safe_float(position[0]), _safe_float(position[1]), 0.0)
        return (0.0, 0.0, 0.0)
    total_x = 0.0
    total_y = 0.0
    total_z = 0.0
    for model in models:
        x, y, z = _model_position(model)
        total_x += x
        total_y += y
        total_z += z
    count = float(len(models))
    return (total_x / count, total_y / count, total_z / count)


def _distance_2d(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dx = float(a[0]) - float(b[0])
    dy = float(a[1]) - float(b[1])
    return ((dx * dx) + (dy * dy)) ** 0.5


def _max_movement(unit: object) -> float:
    models = _alive_models(unit)
    if not models:
        return 0.0
    max_move = 0.0
    for model in models:
        value = getattr(model, "_movement", None)
        if value is None:
            value = getattr(model, "movement", 0)
        max_move = max(max_move, _safe_float(value, 0.0))
    return max_move


def _is_unit_in_engagement_range(unit: object, enemy_units: list[object]) -> bool:
    unit_models = _alive_models(unit)
    if not unit_models:
        return False
    for model in unit_models:
        base = getattr(model, "model_base", None)
        if base is None:
            continue
        for enemy in enemy_units:
            for enemy_model in _alive_models(enemy):
                enemy_base = getattr(enemy_model, "model_base", None)
                if enemy_base is None:
                    continue
                horizontal = _safe_float(base.edge_to_edge_distance(enemy_base), 9999.0)
                vertical = abs(_safe_float(getattr(base, "z", 0.0)) - _safe_float(getattr(enemy_base, "z", 0.0)))
                if horizontal <= float(ENGAGEMENT_RANGE_HORIZONTAL) and vertical <= float(ENGAGEMENT_RANGE_VERTICAL):
                    return True
    return False


def _objective_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    objectives = list(getattr(game_map, "objectives", []) or [])
    entries: list[dict[str, Any]] = []
    for objective in objectives:
        objective_id = str(getattr(objective, "id", "") or "")
        controller = getattr(objective, "controlling_player", None)
        entries.append(
            {
                "objective_id": objective_id,
                "position": [
                    _safe_float(getattr(objective, "x", 0.0), 0.0),
                    _safe_float(getattr(objective, "y", 0.0), 0.0),
                    _safe_float(getattr(objective, "z", 0.0), 0.0),
                ],
                "control_radius": _safe_float(getattr(objective, "control_radius", 0.0), 0.0),
                "controller_player_id": str(getattr(controller, "id", "") or ""),
            }
        )
    entries.sort(key=lambda entry: str(entry["objective_id"]))
    return entries


def _rules_bundle_entry(game: object) -> dict[str, Any]:
    bundle = getattr(game, "ruleset_bundle", None)
    if bundle is None:
        return {}
    payload = {}
    to_dict = getattr(bundle, "to_dict", None)
    if callable(to_dict):
        payload = dict(to_dict() or {})
    rules_bundle_id = getattr(bundle, "rules_bundle_id", None)
    if isinstance(rules_bundle_id, str) and rules_bundle_id:
        payload["rules_bundle_id"] = rules_bundle_id
    return _json_safe(payload)


def _mission_state(game: object) -> dict[str, Any]:
    selected = dict(getattr(game, "selected_mission_info", {}) or {})
    return {
        "secondary_mission_mode": str(getattr(game, "secondary_mission_mode", "") or ""),
        "selected_mission_info": _json_safe(selected),
        "battle_shock_step_active": bool(getattr(game, "battle_shock_step_active", False)),
    }


def _deployment_state(game: object) -> dict[str, Any]:
    deployment_zones = dict(getattr(game, "deployment_zones", {}) or {})
    return {
        "setup_phase": str(getattr(getattr(game, "setup_phase", None), "name", "") or ""),
        "setup_complete": bool(getattr(game, "setup_complete", False)),
        "attacker_index": getattr(game, "attacker_index", None),
        "defender_index": getattr(game, "defender_index", None),
        "deployment_turn_index": _safe_int(getattr(game, "deployment_turn_index", 0), 0),
        "waiting_for_deployment_input": bool(getattr(game, "waiting_for_deployment_input", False)),
        "deployment_notice": str(getattr(game, "deployment_notice", "") or ""),
        "deployment_zone_player_ids": sorted(str(player_id) for player_id in deployment_zones.keys()),
    }


def _terrain_entries(game: object) -> list[dict[str, Any]]:
    game_map = getattr(game, "map", None)
    terrain = list(getattr(game_map, "terrain_features", []) or [])
    entries: list[dict[str, Any]] = []
    for idx, feature in enumerate(terrain):
        feature_id = str(getattr(feature, "id", "") or f"terrain_{idx}")
        terrain_type_obj = getattr(feature, "terrain_type", None)
        terrain_type_name = str(getattr(terrain_type_obj, "name", terrain_type_obj or "") or "")
        footprint = getattr(feature, "footprint", None)
        footprint_coords: list[list[float]] = []
        exterior = getattr(footprint, "exterior", None)
        coords = list(getattr(exterior, "coords", []) or []) if exterior is not None else []
        for coord in coords:
            if len(coord) >= 2:
                footprint_coords.append([_safe_float(coord[0]), _safe_float(coord[1])])
        bounding_box = _json_safe(dict(getattr(feature, "bounding_box", {}) or {}))
        traversal_rules = _json_safe(dict(getattr(feature, "traversal_rules", {}) or {}))
        entries.append(
            {
                "terrain_id": feature_id,
                "terrain_type": terrain_type_name,
                "footprint": footprint_coords,
                "bounding_box": bounding_box,
                "traversal_rules": traversal_rules,
            }
        )
    entries.sort(key=lambda entry: str(entry["terrain_id"]))
    return entries


def _scoring_surfaces(objective_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    for objective in objective_entries:
        objective_id = str(objective.get("objective_id", "") or "")
        surfaces.append(
            {
                "score_source_id": f"score_source:objective:{objective_id}",
                "kind": "OBJECTIVE_CONTROL",
                "objective_id": objective_id,
                "controller_player_id": str(objective.get("controller_player_id", "") or ""),
            }
        )
    surfaces.sort(key=lambda entry: str(entry["score_source_id"]))
    return surfaces


def _control_regions(objective_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    regions: list[dict[str, Any]] = []
    for objective in objective_entries:
        objective_id = str(objective.get("objective_id", "") or "")
        position = list(objective.get("position", [0.0, 0.0, 0.0]) or [0.0, 0.0, 0.0])
        regions.append(
            {
                "region_id": f"region:objective:{objective_id}",
                "kind": "OBJECTIVE_CONTROL_RADIUS",
                "center": [_safe_float(position[0]), _safe_float(position[1]), _safe_float(position[2])],
                "radius": _safe_float(objective.get("control_radius", 0.0), 0.0),
                "objective_id": objective_id,
            }
        )
    regions.sort(key=lambda entry: str(entry["region_id"]))
    return regions


def _objective_ids_in_range(unit: object, objective_entries: list[dict[str, Any]]) -> list[str]:
    in_range: list[str] = []
    for model in _alive_models(unit):
        x, y, _z = _model_position(model)
        base = getattr(model, "model_base", None)
        model_radius = _safe_float(getattr(base, "get_radius", lambda: 0.0)(), 0.0) if base is not None else 0.0
        for objective in objective_entries:
            ox, oy, _oz = objective["position"]
            control_radius = _safe_float(objective["control_radius"], 0.0)
            dx = float(x) - float(ox)
            dy = float(y) - float(oy)
            if ((dx * dx) + (dy * dy)) ** 0.5 <= (control_radius + model_radius):
                in_range.append(str(objective["objective_id"]))
    return sorted(set(in_range))


def _player_card_state(player: object, *, viewer_id: str | None, include_hidden: bool) -> dict[str, Any]:
    active = list(getattr(player, "active_secondaries", []) or [])
    discarded = list(getattr(player, "discarded_secondaries", []) or [])
    deck = list(getattr(player, "secondary_deck", []) or [])
    if include_hidden or str(getattr(player, "id", "") or "") == str(viewer_id or ""):
        return {
            "active_secondary_names": sorted(str(getattr(card, "name", "") or "") for card in active),
            "discarded_secondary_names": sorted(str(getattr(card, "name", "") or "") for card in discarded),
            "secondary_deck_count": int(len(deck)),
        }
    return {
        "active_secondary_count": int(len(active)),
        "discarded_secondary_count": int(len(discarded)),
        "secondary_deck_count": int(len(deck)),
    }


def _player_entry(player: object, *, viewer_id: str | None, include_hidden: bool) -> dict[str, Any]:
    get_score = getattr(player, "get_score", None)
    score = get_score() if callable(get_score) else getattr(player, "score", 0)
    entry = {
        "player_id": str(getattr(player, "id", "") or ""),
        "name": str(getattr(player, "name", "") or ""),
        "command_points": _safe_int(getattr(player, "command_points", 0), 0),
        "score": _safe_int(score, 0),
    }
    entry.update(_player_card_state(player, viewer_id=viewer_id, include_hidden=include_hidden))
    return entry


def _unit_entries(game: object, *, viewer_id: str | None, include_hidden: bool) -> list[dict[str, Any]]:
    objective_entries = _objective_entries(game)
    players = _sorted_players(game)
    units: list[tuple[str, dict[str, Any]]] = []
    for player in players:
        army = getattr(player, "army", None)
        for unit in list(getattr(army, "units", []) or []):
            unit_id = str(get_entity_id(unit))
            models = list(getattr(unit, "models", []) or [])
            alive_models = _alive_models(unit)
            enemies: list[object] = []
            for other_player in players:
                if other_player is player:
                    continue
                other_army = getattr(other_player, "army", None)
                enemies.extend(list(getattr(other_army, "units", []) or []))
            centroid = _unit_centroid(unit)
            enemy_centroids = [_unit_centroid(enemy) for enemy in enemies if enemy is not None]
            objective_centroids = [tuple(objective["position"]) for objective in objective_entries]
            max_move = _max_movement(unit)
            nearest_enemy = min((_distance_2d(centroid, enemy) for enemy in enemy_centroids), default=9999.0)
            nearest_objective = min((_distance_2d(centroid, objective) for objective in objective_centroids), default=9999.0)
            threat_flags = {
                "can_reach_enemy_engagement_this_turn": bool(nearest_enemy <= (max_move + 12.0 + float(ENGAGEMENT_RANGE_HORIZONTAL))),
                "can_reach_score_source_this_turn": bool(nearest_objective <= max_move),
            }
            entry: dict[str, Any] = {
                "unit_id": unit_id,
                "owner_player_id": str(getattr(player, "id", "") or ""),
                "name": str(getattr(unit, "name", "") or ""),
                "model_count": int(len(models)),
                "alive_model_count": int(len(alive_models)),
                "position": [float(centroid[0]), float(centroid[1]), float(centroid[2])],
                "in_engagement_range": bool(_is_unit_in_engagement_range(unit, enemies)),
                "control_region_ids_in_range": [f"region:objective:{oid}" for oid in _objective_ids_in_range(unit, objective_entries)],
                "score_source_ids_in_range": [f"score_source:objective:{oid}" for oid in _objective_ids_in_range(unit, objective_entries)],
                "threat_flags": threat_flags,
            }
            if include_hidden or str(getattr(player, "id", "") or "") == str(viewer_id or ""):
                entry["reserve_status"] = str(getattr(unit, "reserve_status", "") or "")
            units.append((unit_id, entry))
    units.sort(key=lambda item: item[0])
    return [entry for _unit_id, entry in units]


def canonical_omniscient_state(game: object) -> dict[str, Any]:
    players = _sorted_players(game)
    objectives = _objective_entries(game)
    rules_bundle = _rules_bundle_entry(game)
    mission_state = _mission_state(game)
    deployment_state = _deployment_state(game)
    terrain = _terrain_entries(game)
    scoring_surfaces = _scoring_surfaces(objectives)
    control_regions = _control_regions(objectives)
    return {
        "state_blob_version": STATE_BLOB_VERSION,
        "rules_bundle": rules_bundle,
        "battle_round": _battle_round(game),
        "phase": _phase_name(game),
        "active_player_id": _current_player_id(game),
        "players": [_player_entry(player, viewer_id=None, include_hidden=True) for player in players],
        "mission_state": mission_state,
        "deployment_state": deployment_state,
        "objectives": objectives,
        "scoring_surfaces": scoring_surfaces,
        "control_regions": control_regions,
        "terrain": terrain,
        "units": _unit_entries(game, viewer_id=None, include_hidden=True),
    }


def player_obs_state(game: object, player_id: str) -> dict[str, Any]:
    players = _sorted_players(game)
    objectives = _objective_entries(game)
    rules_bundle = _rules_bundle_entry(game)
    mission_state = _mission_state(game)
    deployment_state = _deployment_state(game)
    terrain = _terrain_entries(game)
    scoring_surfaces = _scoring_surfaces(objectives)
    control_regions = _control_regions(objectives)
    return {
        "state_blob_version": STATE_BLOB_VERSION,
        "rules_bundle": rules_bundle,
        "battle_round": _battle_round(game),
        "phase": _phase_name(game),
        "active_player_id": _current_player_id(game),
        "viewer_player_id": str(player_id or ""),
        "players": [
            _player_entry(player, viewer_id=str(player_id or ""), include_hidden=False) for player in players
        ],
        "mission_state": mission_state,
        "deployment_state": deployment_state,
        "objectives": objectives,
        "scoring_surfaces": scoring_surfaces,
        "control_regions": control_regions,
        "terrain": terrain,
        "units": _unit_entries(game, viewer_id=str(player_id or ""), include_hidden=False),
    }


def all_player_obs_states(game: object) -> dict[str, dict[str, Any]]:
    states: dict[str, dict[str, Any]] = {}
    for player in _sorted_players(game):
        player_id = str(getattr(player, "id", "") or "")
        if not player_id:
            continue
        states[player_id] = player_obs_state(game, player_id)
    return states
