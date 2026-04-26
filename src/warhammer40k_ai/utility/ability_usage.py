from __future__ import annotations


START_ANY_PHASE_BATTLESHOCK_CLEAR_PHASE_USAGE = "start_any_phase_clear_battleshock_once_per_phase_used"
START_ANY_PHASE_BATTLESHOCK_CLEAR_TURN_USAGE = "start_any_phase_clear_battleshock_once_per_turn_used"


def phase_name_key(raw: object) -> str:
    return str(raw or "").strip().upper()


def current_turn_key(game: object) -> int:
    try:
        return int(getattr(game, "turn", 0) or 0)
    except (TypeError, ValueError):
        return 0


def current_player_turn_key(game: object) -> str:
    battle_round = current_turn_key(game)
    get_current_player = getattr(game, "get_current_player", None)
    current_player = get_current_player() if callable(get_current_player) else None
    player_id = str(getattr(current_player, "id", "") or "").strip()
    if not player_id:
        try:
            player_id = str(int(getattr(game, "current_player_index", 0) or 0))
        except (TypeError, ValueError):
            player_id = "0"
    return f"{int(battle_round or 0)}:{player_id}"


def unit_has_phase_usage(unit: object, ability_key: str, *, turn: int, phase_name: object, bucket: str) -> bool:
    key = str(ability_key or "").strip().lower()
    phase_key = phase_name_key(phase_name)
    if unit is None or not key or int(turn or 0) <= 0 or not phase_key:
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return False
    used = sr.get(bucket)
    if not isinstance(used, dict):
        return False
    entry = used.get(key)
    if not isinstance(entry, dict):
        return False
    try:
        used_turn = int(entry.get("turn", 0) or 0)
    except (TypeError, ValueError):
        used_turn = 0
    return used_turn == int(turn or 0) and phase_name_key(entry.get("phase_name")) == phase_key


def unit_has_turn_usage(unit: object, ability_key: str, *, turn_key: str, bucket: str) -> bool:
    key = str(ability_key or "").strip().lower()
    turn_key = str(turn_key or "").strip()
    if unit is None or not key or not turn_key:
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        return False
    used = sr.get(bucket)
    if not isinstance(used, dict):
        return False
    return str(used.get(key, "") or "").strip() == turn_key


def mark_unit_phase_usage(unit: object, ability_key: str, *, turn: int, phase_name: object, bucket: str) -> bool:
    key = str(ability_key or "").strip().lower()
    phase_key = phase_name_key(phase_name)
    if unit is None or not key or int(turn or 0) <= 0 or not phase_key:
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    used = dict(sr.get(bucket) or {})
    used[key] = {"turn": int(turn or 0), "phase_name": phase_key}
    sr[bucket] = used
    setattr(unit, "special_rules", sr)
    return True


def mark_unit_turn_usage(unit: object, ability_key: str, *, turn_key: str, bucket: str) -> bool:
    key = str(ability_key or "").strip().lower()
    turn_key = str(turn_key or "").strip()
    if unit is None or not key or not turn_key:
        return False
    sr = getattr(unit, "special_rules", None)
    if not isinstance(sr, dict):
        sr = {}
    used = dict(sr.get(bucket) or {})
    used[key] = turn_key
    sr[bucket] = used
    setattr(unit, "special_rules", sr)
    return True


def alive_model_count(unit: object) -> int:
    if unit is None:
        return 0
    get_models = getattr(unit, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(unit, "models", []) or [])
    total = 0
    for model in models:
        is_alive_attr = getattr(model, "is_alive", False)
        if bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr):
            total += 1
    return int(total)


def unit_visible_to_model(source_model: object, target_unit: object, game_map: object) -> bool:
    if source_model is None or target_unit is None or game_map is None:
        return False
    can_see = getattr(game_map, "can_model_see_model", None)
    if not callable(can_see):
        return False
    get_models = getattr(target_unit, "get_attached_unit_models", None)
    models = list(get_models() or []) if callable(get_models) else list(getattr(target_unit, "models", []) or [])
    for model in models:
        is_alive_attr = getattr(model, "is_alive", False)
        if not bool(is_alive_attr() if callable(is_alive_attr) else is_alive_attr):
            continue
        if bool(can_see(source_model, model)):
            return True
    return False
