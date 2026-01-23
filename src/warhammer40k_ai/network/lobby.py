from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple
import uuid

PLAYER_SLOTS = ("player1", "player2")
ROLE_SPECTATOR = "spectator"


@dataclass(frozen=True)
class ArmyState:
    status: str = "none"  # none | pending | validated | invalid
    list_name: Optional[str] = None
    error: Optional[str] = None
    army: Optional[Any] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "list_name": self.list_name,
            "error": self.error,
        }


@dataclass(frozen=True)
class SlotState:
    slot: str
    connection_id: Optional[str] = None
    display_name: str = ""
    ready: bool = False
    token: Optional[str] = None
    army: ArmyState = field(default_factory=ArmyState)

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "connected": self.connection_id is not None,
            "ready": bool(self.ready),
            "army": self.army.to_dict(),
        }

    def is_assigned(self) -> bool:
        return self.token is not None


@dataclass(frozen=True)
class SpectatorState:
    token: str
    display_name: str
    connection_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "display_name": self.display_name,
            "connected": self.connection_id is not None,
        }


@dataclass(frozen=True)
class ConnectionState:
    connection_id: str
    display_name: str = ""
    token: Optional[str] = None
    role: Optional[str] = None
    authorized: bool = False


@dataclass(frozen=True)
class LobbyState:
    session_id: str
    join_code: Optional[str] = None
    locked: bool = False
    started: bool = False
    players: Dict[str, SlotState] = field(default_factory=dict)
    spectators: List[SpectatorState] = field(default_factory=list)
    connections: Dict[str, ConnectionState] = field(default_factory=dict)

    def to_payload(self) -> dict:
        return {
            "session_id": self.session_id,
            "locked": bool(self.locked),
            "started": bool(self.started),
            "players": {slot: state.to_dict() for slot, state in self.players.items()},
            "spectators": [s.to_dict() for s in list(self.spectators or [])],
        }


@dataclass(frozen=True)
class LobbyActionResult:
    state: LobbyState
    errors: List[str] = field(default_factory=list)
    response: Optional[dict] = None

    @property
    def ok(self) -> bool:
        return not self.errors


def new_lobby_state(*, join_code: Optional[str] = None) -> LobbyState:
    players = {slot: SlotState(slot=slot) for slot in PLAYER_SLOTS}
    return LobbyState(session_id=uuid.uuid4().hex, join_code=join_code, players=players)


def _replace_state(state: LobbyState, **kwargs: Any) -> LobbyState:
    return replace(state, **kwargs)


def _update_connection(state: LobbyState, connection: ConnectionState) -> LobbyState:
    connections = dict(state.connections)
    connections[connection.connection_id] = connection
    return _replace_state(state, connections=connections)


def _remove_connection(state: LobbyState, connection_id: str) -> LobbyState:
    connections = dict(state.connections)
    connections.pop(connection_id, None)
    return _replace_state(state, connections=connections)


def register_connection(state: LobbyState, connection_id: str) -> LobbyState:
    if connection_id in state.connections:
        return state
    connection = ConnectionState(connection_id=connection_id, display_name="Guest", authorized=False)
    return _update_connection(state, connection)


def disconnect_connection(state: LobbyState, connection_id: str) -> LobbyState:
    connection = state.connections.get(connection_id)
    if connection is None:
        return state
    players = dict(state.players)
    for slot, slot_state in players.items():
        if slot_state.connection_id == connection_id:
            players[slot] = replace(slot_state, connection_id=None, ready=False)
    spectators = list(state.spectators or [])
    spectators = [
        replace(s, connection_id=None) if s.connection_id == connection_id else s
        for s in spectators
    ]
    next_state = _replace_state(state, players=players, spectators=spectators)
    return _remove_connection(next_state, connection_id)


def apply_hello(state: LobbyState, connection_id: str, display_name: str) -> LobbyState:
    connection = state.connections.get(connection_id)
    if connection is None:
        return state
    display_name = str(display_name or "").strip() or connection.display_name
    next_state = _update_connection(state, replace(connection, display_name=display_name))
    players = dict(next_state.players)
    for slot, slot_state in players.items():
        if slot_state.connection_id == connection_id:
            players[slot] = replace(slot_state, display_name=display_name)
    spectators = [
        replace(s, display_name=display_name) if s.connection_id == connection_id else s
        for s in list(next_state.spectators or [])
    ]
    return _replace_state(next_state, players=players, spectators=spectators)


def _find_slot_by_token(state: LobbyState, token: str) -> Optional[str]:
    for slot, slot_state in state.players.items():
        if slot_state.token == token:
            return slot
    return None


def _find_spectator_by_token(state: LobbyState, token: str) -> Optional[int]:
    for idx, spectator in enumerate(list(state.spectators or [])):
        if spectator.token == token:
            return idx
    return None


def apply_auth(
    state: LobbyState,
    connection_id: str,
    *,
    join_code: Optional[str] = None,
    reconnect_token: Optional[str] = None,
) -> LobbyActionResult:
    connection = state.connections.get(connection_id)
    if connection is None:
        return LobbyActionResult(state=state, errors=["Unknown connection."])
    if state.join_code and join_code != state.join_code:
        return LobbyActionResult(state=state, errors=["Invalid join code."])

    if reconnect_token:
        reconnect_token = str(reconnect_token)
        slot = _find_slot_by_token(state, reconnect_token)
        if slot is not None:
            slot_state = state.players[slot]
            players = dict(state.players)
            players[slot] = replace(slot_state, connection_id=connection_id)
            next_state = _replace_state(state, players=players)
            next_state = _update_connection(
                next_state,
                replace(connection, token=reconnect_token, role=slot, authorized=True),
            )
            response = {"ok": True, "token": reconnect_token, "session_id": state.session_id, "role": slot}
            return LobbyActionResult(state=next_state, response=response)
        spec_index = _find_spectator_by_token(state, reconnect_token)
        if spec_index is not None:
            spectators = list(state.spectators or [])
            spectator = spectators[spec_index]
            spectators[spec_index] = replace(spectator, connection_id=connection_id)
            next_state = _replace_state(state, spectators=spectators)
            next_state = _update_connection(
                next_state,
                replace(connection, token=reconnect_token, role=ROLE_SPECTATOR, authorized=True),
            )
            response = {
                "ok": True,
                "token": reconnect_token,
                "session_id": state.session_id,
                "role": ROLE_SPECTATOR,
            }
            return LobbyActionResult(state=next_state, response=response)
        return LobbyActionResult(state=state, errors=["Reconnect token not recognized."])

    token = uuid.uuid4().hex
    next_state = _update_connection(state, replace(connection, token=token, authorized=True))
    response = {"ok": True, "token": token, "session_id": state.session_id}
    return LobbyActionResult(state=next_state, response=response)


def _release_connection_role(state: LobbyState, connection: ConnectionState) -> LobbyState:
    if connection.role is None:
        return state
    if connection.role in PLAYER_SLOTS:
        slot_state = state.players.get(connection.role)
        if slot_state is None:
            return state
        players = dict(state.players)
        players[connection.role] = SlotState(slot=connection.role)
        return _replace_state(state, players=players)
    if connection.role == ROLE_SPECTATOR:
        spectators = [
            s for s in list(state.spectators or []) if s.token != connection.token
        ]
        return _replace_state(state, spectators=spectators)
    return state


def apply_role_select(state: LobbyState, connection_id: str, role: str) -> LobbyActionResult:
    connection = state.connections.get(connection_id)
    if connection is None:
        return LobbyActionResult(state=state, errors=["Unknown connection."])
    if not connection.authorized or not connection.token:
        return LobbyActionResult(state=state, errors=["Not authorized."])
    role = str(role or "").strip()
    if role not in PLAYER_SLOTS and role != ROLE_SPECTATOR:
        return LobbyActionResult(state=state, errors=["Invalid role selection."])

    if state.locked and role in PLAYER_SLOTS and connection.role != role:
        return LobbyActionResult(state=state, errors=["Lobby locked."])

    next_state = _release_connection_role(state, connection)

    if role in PLAYER_SLOTS:
        slot_state = next_state.players.get(role)
        if slot_state is None:
            return LobbyActionResult(state=state, errors=["Unknown player slot."])
        if slot_state.token and slot_state.token != connection.token:
            return LobbyActionResult(state=state, errors=["Player slot already taken."])
        players = dict(next_state.players)
        if slot_state.token == connection.token:
            players[role] = replace(slot_state, connection_id=connection_id, display_name=connection.display_name)
        else:
            players[role] = SlotState(
                slot=role,
                connection_id=connection_id,
                display_name=connection.display_name,
                ready=False,
                token=connection.token,
                army=ArmyState(),
            )
        next_state = _replace_state(next_state, players=players)
        next_state = _update_connection(next_state, replace(connection, role=role))
        return LobbyActionResult(state=next_state, response={"ok": True, "role": role})

    spectators = list(next_state.spectators or [])
    existing_index = _find_spectator_by_token(next_state, connection.token)
    if existing_index is not None:
        spectators[existing_index] = replace(
            spectators[existing_index],
            connection_id=connection_id,
            display_name=connection.display_name,
        )
    else:
        spectators.append(
            SpectatorState(
                token=connection.token,
                display_name=connection.display_name,
                connection_id=connection_id,
            )
        )
    next_state = _replace_state(next_state, spectators=spectators)
    next_state = _update_connection(next_state, replace(connection, role=ROLE_SPECTATOR))
    return LobbyActionResult(state=next_state, response={"ok": True, "role": ROLE_SPECTATOR})


def apply_ready(state: LobbyState, connection_id: str, ready: bool) -> LobbyActionResult:
    connection = state.connections.get(connection_id)
    if connection is None:
        return LobbyActionResult(state=state, errors=["Unknown connection."])
    if connection.role not in PLAYER_SLOTS:
        return LobbyActionResult(state=state, errors=["Only players can ready up."])
    slot_state = state.players.get(connection.role)
    if slot_state is None:
        return LobbyActionResult(state=state, errors=["Unknown player slot."])
    players = dict(state.players)
    players[connection.role] = replace(slot_state, ready=bool(ready))
    next_state = _replace_state(state, players=players)
    return LobbyActionResult(state=next_state, response={"ok": True, "ready": bool(ready)})


def apply_army_state(state: LobbyState, slot: str, army_state: ArmyState) -> LobbyState:
    if slot not in state.players:
        return state
    players = dict(state.players)
    players[slot] = replace(state.players[slot], army=army_state)
    return _replace_state(state, players=players)


def is_ready_to_start(state: LobbyState) -> bool:
    if state.locked or state.started:
        return False
    for slot in PLAYER_SLOTS:
        slot_state = state.players.get(slot)
        if slot_state is None:
            return False
        if not slot_state.is_assigned():
            return False
        if slot_state.connection_id is None:
            return False
        if not slot_state.ready:
            return False
        if slot_state.army.status != "validated":
            return False
    return True


def lock_lobby(state: LobbyState) -> LobbyState:
    return _replace_state(state, locked=True)


def mark_started(state: LobbyState) -> LobbyState:
    return _replace_state(state, locked=True, started=True)
