from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..engine.commands import GameCommand
from .control import build_control_message
from .messages import CommandMessage, parse_message
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

    async def connect(self) -> None:
        await self.transport.connect()

    async def close(self) -> None:
        await self.transport.close()

    async def send_control(self, message_type: str, payload: dict) -> None:
        await self.transport.send(build_control_message(message_type, payload))

    async def send_hello(self, display_name: str) -> None:
        await self.send_control("hello", {"display_name": display_name})

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
        return await self.transport.next_message(timeout=timeout)

    def handle_message(self, event) -> None:
        msg = event.message
        if event.category == "control":
            msg_type = msg.get("type")
            payload = msg.get("payload", {})
            if msg_type == "auth" and payload.get("ok"):
                self.session_token = payload.get("token") or self.session_token
                self.session_id = payload.get("session_id") or self.session_id
                if payload.get("role"):
                    self.role = payload.get("role")
            if msg_type == "role_select" and payload.get("ok") and payload.get("role"):
                self.role = payload.get("role")
            if msg_type == "lobby_state":
                self.lobby_state = dict(payload)
            return

        parsed = parse_message(msg)
        if parsed is None:
            return
        msg_type = msg.get("type")
        if msg_type == "snapshot":
            snapshot = msg.get("payload", {}).get("snapshot", {})
            players = list(snapshot.get("players", []) or [])
            if self.role == "player1" and players:
                self.player_id = players[0].get("id", self.player_id)
            if self.role == "player2" and len(players) > 1:
                self.player_id = players[1].get("id", self.player_id)
            events = list(snapshot.get("events", []) or [])
            if events:
                self.event_cursor.last_event_id = 0
                self.event_cursor.validate_and_advance(events)
            return
        if msg_type == "resync":
            payload = msg.get("payload", {})
            snapshot = payload.get("snapshot", {}) or {}
            players = list(snapshot.get("players", []) or [])
            if self.role == "player1" and players:
                self.player_id = players[0].get("id", self.player_id)
            if self.role == "player2" and len(players) > 1:
                self.player_id = players[1].get("id", self.player_id)
            events = list(payload.get("events", []) or [])
            since_event_id = payload.get("since_event_id")
            if events:
                first_event_id = events[0].get("event_id")
                if first_event_id is not None:
                    self.event_cursor.last_event_id = int(first_event_id) - 1
                else:
                    self.event_cursor.last_event_id = int(since_event_id or 0)
                self.event_cursor.validate_and_advance(events)
            else:
                self.event_cursor.last_event_id = int(since_event_id or 0)
            return
        if msg_type == "event":
            events = list(msg.get("payload", {}).get("events", []) or [])
            if events:
                self.event_cursor.validate_and_advance(events)
