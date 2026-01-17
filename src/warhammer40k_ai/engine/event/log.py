from collections import deque
from typing import Dict, Deque, List

_ACTIONS: Dict[str, Deque[str]] = {}
_DICE: Dict[str, Deque[str]] = {}

_MAX_ENTRIES = 200

def _get_queue(store: Dict[str, Deque[str]], player_name: str) -> Deque[str]:
    if player_name not in store:
        store[player_name] = deque(maxlen=_MAX_ENTRIES)
    return store[player_name]

def append_action(player_name: str, text: str) -> None:
    q = _get_queue(_ACTIONS, player_name)
    q.append(text)

def append_dice(player_name: str, text: str) -> None:
    q = _get_queue(_DICE, player_name)
    q.append(text)

def get_recent_actions(player_name: str, limit: int = 20) -> List[str]:
    q = _get_queue(_ACTIONS, player_name)
    return list(q)[-limit:]

def get_recent_dice(player_name: str, limit: int = 20) -> List[str]:
    q = _get_queue(_DICE, player_name)
    return list(q)[-limit:]


