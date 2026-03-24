from collections import deque
from typing import Dict, Deque, List

from ...utility.entity_ids import get_entity_id

_ACTIONS: Dict[str, Deque[str]] = {}
_DICE: Dict[str, Deque[str]] = {}

_MAX_ENTRIES = 200

def _resolve_player_id(player_or_id: object) -> str:
    if isinstance(player_or_id, str):
        return player_or_id
    return get_entity_id(player_or_id)


def _get_queue(store: Dict[str, Deque[str]], player_id: str) -> Deque[str]:
    if player_id not in store:
        store[player_id] = deque(maxlen=_MAX_ENTRIES)
    return store[player_id]

def append_action(player_or_id: object, text: str) -> None:
    player_id = _resolve_player_id(player_or_id)
    q = _get_queue(_ACTIONS, player_id)
    q.append(text)

def append_dice(player_or_id: object, text: str) -> None:
    player_id = _resolve_player_id(player_or_id)
    q = _get_queue(_DICE, player_id)
    q.append(text)

def clear_recent_logs(player_or_id: object | None = None) -> None:
    if player_or_id is None:
        _ACTIONS.clear()
        _DICE.clear()
        return
    player_id = _resolve_player_id(player_or_id)
    _ACTIONS.pop(player_id, None)
    _DICE.pop(player_id, None)

def get_recent_actions(player_or_id: object, limit: int = 20) -> List[str]:
    player_id = _resolve_player_id(player_or_id)
    q = _get_queue(_ACTIONS, player_id)
    return list(q)[-limit:]

def get_recent_dice(player_or_id: object, limit: int = 20) -> List[str]:
    player_id = _resolve_player_id(player_or_id)
    q = _get_queue(_DICE, player_id)
    return list(q)[-limit:]
