from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Optional

from ..engine.command_dispatcher import CommandResult
from ..engine.command_kinds import CMD_REQUEST_DECISION
from ..engine.commands import GameCommand
from ..engine.decisions import DecisionRequest
from ..engine.event_log import DeterministicEventLog
from ..engine.snapshot import load_game_snapshot
from ..engine.ref_codec import encode_refs
from ..roster.player import PlayerControl
from .client import NetworkClient
from .messages import CommandMessage, ErrorMessage, parse_message


def _strip_ref_wrappers(value: Any) -> Any:
    if isinstance(value, dict):
        if "__ref__" in value:
            ref = value.get("__ref__") or {}
            return ref.get("id")
        if "__enum__" in value:
            enum_info = value.get("__enum__") or {}
            return enum_info.get("name")
        if "__modifier__" in value:
            return value
        return {str(k): _strip_ref_wrappers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_strip_ref_wrappers(v) for v in value]
    return value


def _normalize_decision_payload(payload: dict) -> dict:
    encoded = encode_refs(payload)
    return _strip_ref_wrappers(encoded)


def _current_event_id(game: object) -> int:
    event_log = getattr(game, "event_log", None)
    if event_log is None or not getattr(event_log, "events", None):
        return 0
    return int(event_log.events[-1].event_id)


@dataclass
class GameUpdate:
    game: object
    game_proxy: object


class NetworkGameProxy:
    def __init__(self, session: "NetworkGameSession", game: object):
        self._session = session
        self._game = game

    def __getattr__(self, name: str) -> Any:
        return getattr(self._game, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"_session", "_game"}:
            object.__setattr__(self, name, value)
            return
        setattr(self._game, name, value)

    def apply_command(self, command: GameCommand):
        cmd = self._session.ensure_player_id(command)
        if not self._session.allow_commands:
            return CommandResult(
                command_id=cmd.command_id,
                kind=cmd.kind,
                ok=False,
                errors=("Spectators cannot issue commands.",),
            )
        result = self._game.apply_command(cmd)
        if getattr(result, "ok", False):
            self._session.record_applied(cmd.command_id)
            self._session.queue_command(cmd)
        return result

    def request_decision(self, request: DecisionRequest) -> None:
        if request is None:
            return None
        if not self._session.allow_commands:
            return None
        decision_payload = _normalize_decision_payload(request.to_dict())
        player_id = request.player_id or self._session.client.player_id
        cmd = GameCommand.create(
            CMD_REQUEST_DECISION,
            player_id=player_id,
            payload={"decision": decision_payload},
        )
        result = self._game.apply_command(cmd)
        if getattr(result, "ok", False):
            self._session.record_applied(cmd.command_id)
            self._session.queue_command(cmd)
        return None


class NetworkGameSession:
    def __init__(
        self,
        client: NetworkClient,
        *,
        allow_commands: bool = True,
        applied_limit: int = 2000,
    ) -> None:
        self.client = client
        self.allow_commands = bool(allow_commands)
        self._applied_limit = max(100, int(applied_limit))
        self._applied_ids: set[str] = set()
        self._applied_order: Deque[str] = deque()
        self._outgoing: Deque[GameCommand] = deque()
        self.game: Optional[object] = None
        self.game_proxy: Optional[NetworkGameProxy] = None
        self.game_version = 0
        self.last_error: Optional[str] = None
        self.on_game_loaded: Optional[Callable[[GameUpdate], None]] = None

    def ensure_player_id(self, command: GameCommand) -> GameCommand:
        if command.player_id is not None:
            return command
        player_id = self.client.player_id
        if player_id is None:
            return command
        return GameCommand(
            command_id=command.command_id,
            kind=command.kind,
            player_id=player_id,
            payload=command.payload,
            metadata=command.metadata,
            created_at=command.created_at,
        )

    def record_applied(self, command_id: str) -> None:
        if not command_id:
            return
        if command_id in self._applied_ids:
            return
        self._applied_ids.add(command_id)
        self._applied_order.append(command_id)
        while len(self._applied_order) > self._applied_limit:
            oldest = self._applied_order.popleft()
            self._applied_ids.discard(oldest)

    def queue_command(self, command: GameCommand) -> None:
        if command is None:
            return
        self._outgoing.append(command)

    async def flush_outgoing(self) -> None:
        while self._outgoing:
            cmd = self._outgoing.popleft()
            await self.client.send_command(cmd, omit_event_id=True)

    def _apply_local_control(self, game: object) -> None:
        role = getattr(self.client, "role", None)
        if role not in ("player1", "player2"):
            return
        players = list(getattr(game, "players", []) or [])
        index = 0 if role == "player1" else 1
        for idx, player in enumerate(players):
            if idx == index:
                player.control = PlayerControl.LOCAL
            else:
                player.control = PlayerControl.REMOTE

    def _build_game(self, snapshot: dict, events_tail: Optional[list[dict]] = None) -> object:
        game = load_game_snapshot(snapshot)
        if events_tail is not None:
            existing_log = getattr(game, "event_log", None)
            if existing_log is not None:
                existing_log.detach()
            game.event_log = DeterministicEventLog.from_payload(list(events_tail or []))
            game.event_log.attach(game)
        try:
            game.is_authoritative = False
        except Exception:
            pass
        self._apply_local_control(game)
        return game

    def _set_game(self, game: object) -> None:
        self.game = game
        self.game_proxy = NetworkGameProxy(self, game)
        self.game_version += 1
        self._applied_ids.clear()
        self._applied_order.clear()
        if self.on_game_loaded is not None:
            self.on_game_loaded(GameUpdate(game=game, game_proxy=self.game_proxy))

    async def request_resync(self) -> None:
        token = self.client.session_token
        if token is None:
            return
        await self.client.send_auth(reconnect_token=token, last_event_id=self.client.event_cursor.last_event_id)

    async def handle_message(self, event) -> None:
        self.client.handle_message(event)
        if event.category != "game":
            return
        msg_type = event.message_type
        payload = event.message.get("payload", {}) if isinstance(event.message, dict) else {}

        if msg_type == "snapshot":
            snapshot = payload.get("snapshot", {}) or {}
            self._set_game(self._build_game(snapshot))
            return

        if msg_type == "resync":
            snapshot = payload.get("snapshot", {}) or {}
            events = list(payload.get("events", []) or [])
            self._set_game(self._build_game(snapshot, events_tail=events))
            return

        if msg_type == "command":
            parsed = parse_message(event.message)
            if isinstance(parsed, CommandMessage):
                command = parsed.command
                if command.command_id not in self._applied_ids and self.game is not None:
                    self.game.apply_command(command)
                    self.record_applied(command.command_id)
            return

        if msg_type == "error":
            parsed = parse_message(event.message)
            if isinstance(parsed, ErrorMessage):
                self.last_error = "; ".join(parsed.errors)
                await self.request_resync()

    async def poll_messages(self) -> None:
        while True:
            try:
                event = await self.client.next_message(timeout=0.0)
            except asyncio.TimeoutError:
                break
            await self.handle_message(event)

    def current_event_id(self) -> int:
        if self.game is None:
            return 0
        return _current_event_id(self.game)
