from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..engine.commands import GameCommand
from ..version import get_app_version
from .control import build_control_message
from .messages import CommandMessage, parse_message
from .debug import log_network
from .protocol import EventStreamCursor
from .transport import TransportClient, build_client_ssl_context


class NetworkClient:
    def __init__(
        self,
        *,
        uri: str,
        ca_cert: Optional[str] = None,
        insecure: bool = False,
        ping_interval: float = 20.0,
        ping_timeout: float = 20.0,
        max_message_size: int = 1_000_000,
    ) -> None:
        ssl_context = None
        if uri.startswith("wss://"):
            ssl_context = build_client_ssl_context(ca_cert=ca_cert, insecure=insecure)
        self.transport = TransportClient(
            uri=uri,
            ssl_context=ssl_context,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            max_message_size=max_message_size,
        )
        self.session_token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.role: Optional[str] = None
        self.lobby_state: Optional[dict] = None
        self.event_cursor = EventStreamCursor()
        self.player_id: Optional[str] = None
        self._pending_messages: list[Any] = []
        self.client_version = get_app_version()
        self.server_version: Optional[str] = None
        self.version_ok: Optional[bool] = None
        self.version_error: Optional[str] = None

    async def connect(self) -> None:
        await self.transport.connect()

    async def close(self) -> None:
        await self.transport.close()

    async def send_control(self, message_type: str, payload: dict) -> None:
        await self.transport.send(build_control_message(message_type, payload))

    async def send_hello(self, display_name: str, *, app_version: Optional[str] = None) -> None:
        payload = {
            "display_name": display_name,
            "app_version": str(app_version or self.client_version),
        }
        await self.send_control("hello", payload)

    async def send_auth(
        self,
        *,
        join_code: Optional[str] = None,
        reconnect_token: Optional[str] = None,
        last_event_id: Optional[int] = None,
    ) -> None:
        payload = {}
        if join_code:
            payload["join_code"] = join_code
        if reconnect_token:
            payload["reconnect_token"] = reconnect_token
        if last_event_id is not None:
            payload["last_event_id"] = int(last_event_id)
        await self.send_control("auth", payload)

    async def send_role_select(self, role: str) -> None:
        await self.send_control("role_select", {"role": role})

    async def send_ready(self, ready: bool) -> None:
        await self.send_control("ready", {"ready": bool(ready)})

    async def send_army_submit(self, list_text: str, *, list_name: str = "army_list") -> None:
        await self.send_control("army_submit", {"list_name": list_name, "list_text": list_text})

    async def send_command(self, command: GameCommand, *, omit_event_id: bool = False) -> None:
        if self.role == "spectator":
            raise RuntimeError("Spectators cannot send commands.")
        if command.player_id is None and self.player_id is not None:
            command = GameCommand(
                command_id=command.command_id,
                kind=command.kind,
                player_id=self.player_id,
                payload=command.payload,
                metadata=command.metadata,
                created_at=command.created_at,
            )
        client_last_event_id = None if omit_event_id else self.event_cursor.last_event_id
        message = CommandMessage(command=command, client_last_event_id=client_last_event_id)
        await self.transport.send(message)

    async def next_message(self, *, timeout: Optional[float] = None):
        if self._pending_messages:
            return self._pending_messages.pop(0)
        if timeout == 0.0:
            event = self.transport.try_next_message()
            if event is None:
                raise asyncio.TimeoutError
            return event
        return await self.transport.next_message(timeout=timeout)

    def handle_message(self, event) -> None:
        log_network(
            "client.recv",
            category=getattr(event, "category", None),
            type=getattr(event, "message_type", None),
        )
        msg = event.message
        if event.category == "control":
            msg_type = msg.get("type")
            payload = msg.get("payload", {})
            if msg_type == "hello":
                log_network(
                    "client.control.hello",
                    ok=payload.get("ok"),
                    server_version=payload.get("server_version"),
                    client_version=payload.get("client_version"),
                    errors=payload.get("errors"),
                )
                self.server_version = payload.get("server_version") or self.server_version
                ok = payload.get("ok")
                if ok is False:
                    errors = payload.get("errors", [])
                    self.version_error = "; ".join(str(e) for e in errors if e) or "Version mismatch."
                    self.version_ok = False
                else:
                    if self.server_version and self.server_version != self.client_version:
                        self.version_error = (
                            f"Version mismatch (client {self.client_version}, server {self.server_version})."
                        )
                        self.version_ok = False
                    else:
                        self.version_ok = True
                return
            if msg_type == "auth" and payload.get("ok"):
                log_network(
                    "client.control.auth",
                    ok=payload.get("ok"),
                    session_id=payload.get("session_id"),
                    role=payload.get("role"),
                    errors=payload.get("errors"),
                )
                self.session_token = payload.get("token") or self.session_token
                self.session_id = payload.get("session_id") or self.session_id
                if payload.get("role"):
                    self.role = payload.get("role")
            if msg_type == "role_select" and payload.get("ok") and payload.get("role"):
                log_network("client.control.role_select", ok=payload.get("ok"), role=payload.get("role"))
                self.role = payload.get("role")
            if msg_type == "lobby_state":
                log_network(
                    "client.control.lobby_state",
                    session_id=payload.get("session_id"),
                    started=payload.get("started"),
                )
                self.lobby_state = dict(payload)
            return

        parsed = parse_message(msg)
        if parsed is None:
            return
        msg_type = msg.get("type")
        if msg_type == "snapshot":
            snapshot = msg.get("payload", {}).get("snapshot", {})
            log_network(
                "client.game.snapshot",
                players=len(list(snapshot.get("players", []) or [])),
                setup_phase=(snapshot.get("game", {}) or {}).get("setup_phase"),
            )
            players = list(snapshot.get("players", []) or [])
            if self.role == "player1" and players:
                self.player_id = players[0].get("id", self.player_id)
            if self.role == "player2" and len(players) > 1:
                self.player_id = players[1].get("id", self.player_id)
            events = list(snapshot.get("events", []) or [])
            prev_event_id = self.event_cursor.last_event_id
            if events:
                self.event_cursor.last_event_id = 0
                self.event_cursor.validate_and_advance(events)
            log_network(
                "client.game.snapshot.cursor",
                previous=prev_event_id,
                current=self.event_cursor.last_event_id,
            )
            return
        if msg_type == "resync":
            payload = msg.get("payload", {})
            snapshot = payload.get("snapshot", {}) or {}
            log_network(
                "client.game.resync",
                reason=payload.get("reason"),
                since_event_id=payload.get("since_event_id"),
                setup_phase=(snapshot.get("game", {}) or {}).get("setup_phase"),
                events=len(list(payload.get("events", []) or [])),
            )
            players = list(snapshot.get("players", []) or [])
            if self.role == "player1" and players:
                self.player_id = players[0].get("id", self.player_id)
            if self.role == "player2" and len(players) > 1:
                self.player_id = players[1].get("id", self.player_id)
            events = list(payload.get("events", []) or [])
            since_event_id = payload.get("since_event_id")
            prev_event_id = self.event_cursor.last_event_id
            if events:
                first_event_id = events[0].get("event_id")
                if first_event_id is not None:
                    self.event_cursor.last_event_id = int(first_event_id) - 1
                else:
                    self.event_cursor.last_event_id = int(since_event_id or 0)
                self.event_cursor.validate_and_advance(events)
            else:
                self.event_cursor.last_event_id = int(since_event_id or 0)
            log_network(
                "client.game.resync.cursor",
                previous=prev_event_id,
                current=self.event_cursor.last_event_id,
            )
            return
        if msg_type == "event":
            events = list(msg.get("payload", {}).get("events", []) or [])
            log_network("client.game.event", count=len(events))
            if events:
                prev_event_id = self.event_cursor.last_event_id
                self.event_cursor.validate_and_advance(events)
                log_network(
                    "client.game.event.cursor",
                    previous=prev_event_id,
                    current=self.event_cursor.last_event_id,
                )
