from __future__ import annotations

from typing import Any


STATE_BLOB_VERSION = "1.3.0"


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, set):
        items = [json_safe(v) for v in value]
        return sorted(items, key=lambda item: str(item))
    return str(value)


def phase_name(game: object) -> str:
    phase = getattr(game, "phase", None)
    name = getattr(phase, "name", None)
    if isinstance(name, str) and name:
        return name
    return str(phase or "")


def battle_round(game: object) -> int:
    getter = getattr(game, "get_battle_round", None)
    if callable(getter):
        return safe_int(getter(), 0)
    return safe_int(getattr(game, "turn", 0), 0)


def current_player_id(game: object) -> str:
    getter = getattr(game, "get_current_player", None)
    if not callable(getter):
        return ""
    player = getter()
    return str(getattr(player, "id", "") or "")


def sorted_players(game: object) -> list[object]:
    players = list(getattr(game, "players", []) or [])
    return sorted(players, key=lambda player: str(getattr(player, "id", "") or ""))


def rules_bundle_entry(game: object) -> dict[str, Any]:
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
    return json_safe(payload)


__all__ = [
    "STATE_BLOB_VERSION",
    "battle_round",
    "current_player_id",
    "json_safe",
    "phase_name",
    "rules_bundle_entry",
    "safe_float",
    "safe_int",
    "sorted_players",
]
