from __future__ import annotations

import asyncio
import ssl
from typing import Any, Dict, Optional

from ..engine.game import Battlefield, BattlefieldSize, Game
from ..battlefield.map import Map
from ..engine.event_log import DeterministicEventLog
from ..engine.commands import GameCommand
from ..engine.command_dispatcher import CommandResult
from ..roster.player import Player, PlayerControl
from ..roster.army import ArmyValidationError, parse_army_list_text
from ..waha_helper import WahaHelper
from .control import build_control_message, parse_control_message
from .lobby import (
    ArmyState,
    LobbyActionResult,
    LobbyState,
    PLAYER_SLOTS,
    ROLE_SPECTATOR,
    apply_army_state,
    apply_auth,
    apply_hello,
    apply_ready,
    apply_role_select,
    disconnect_connection,
    is_ready_to_start,
    mark_started,
    new_lobby_state,
    register_connection,
)
from .messages import CommandMessage, ErrorMessage, EventMessage, ResyncMessage, SnapshotMessage, parse_message
from .protocol import build_resync_message, build_snapshot_message, handle_command_message
from .transport import TransportServer, build_server_ssl_context


class NetworkServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        cert_path: Optional[str],
        key_path: Optional[str],
        join_code: Optional[str] = None,
        ping_interval: float = 20.0,
        ping_timeout: float = 20.0,
        max_message_size: int = 1_000_000,
    ) -> None:
        ssl_context = None
        if cert_path or key_path:
            if not cert_path or not key_path:
                raise ValueError("Both cert and key paths are required for TLS.")
            ssl_context = build_server_ssl_context(cert_path, key_path)
        self.transport = TransportServer(
            host=host,
            port=port,
            ssl_context=ssl_context,
            ping_interval=ping_interval,
            ping_timeout=ping_timeout,
            max_message_size=max_message_size,
        )
        self._running = False
        self._state = new_lobby_state(join_code=join_code)
        self._game: Optional[Game] = None
        self._player_ids: Dict[str, str] = {}
        self._waha_helper = WahaHelper()

    @property
    def lobby_state(self) -> LobbyState:
        return self._state

    @property
    def game(self) -> Optional[Game]:
        return self._game

    async def start(self) -> None:
        await self.transport.start()
        self._running = True

    async def stop(self) -> None:
        self._running = False
        await self.transport.stop()

    async def run(self) -> None:
        if not self._running:
            raise RuntimeError("Server not started.")
        while self._running:
            message_task = asyncio.create_task(self.transport.next_message())
            connection_task = asyncio.create_task(self.transport.next_connection_event())
            done, pending = await asyncio.wait(
                [message_task, connection_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                result = task.result()
                if result is None:
                    continue
                if hasattr(result, "event"):
                    await self._handle_connection_event(result)
                else:
                    await self._handle_transport_event(result)

    async def _handle_connection_event(self, event) -> None:
        if event.event == "connected":
            self._state = register_connection(self._state, event.connection_id)
            await self._broadcast_lobby_state()
            return
        if event.event == "disconnected":
            self._state = disconnect_connection(self._state, event.connection_id)
            await self._broadcast_lobby_state()
            return

    async def _handle_transport_event(self, event) -> None:
        if event.category == "control":
            await self._handle_control_event(event.connection_id, event.message)
            return
        await self._handle_game_event(event.connection_id, event.message)

    async def _handle_control_event(self, connection_id: str, message: dict) -> None:
        msg_type, payload = parse_control_message(message)
        if msg_type == "hello":
            display_name = payload.get("display_name", "")
            self._state = apply_hello(self._state, connection_id, display_name)
            await self._send_control(connection_id, "hello", {"ok": True, "server": "warhammer40k_ai"})
            await self._broadcast_lobby_state()
            return
        if msg_type == "auth":
            result = apply_auth(
                self._state,
                connection_id,
                join_code=payload.get("join_code"),
                reconnect_token=payload.get("reconnect_token"),
            )
            self._state = result.state
            if result.ok:
                await self._send_control(connection_id, "auth", result.response or {"ok": True})
                await self._broadcast_lobby_state()
                if self._game is not None:
                    await self._send_snapshot_or_resync(connection_id, payload)
            else:
                await self._send_control(connection_id, "auth", {"ok": False, "errors": list(result.errors)})
            return
        if msg_type == "role_select":
            result = apply_role_select(self._state, connection_id, payload.get("role"))
            self._state = result.state
            await self._send_control(
                connection_id,
                "role_select",
                result.response or {"ok": result.ok, "errors": list(result.errors)},
            )
            if result.ok:
                await self._broadcast_lobby_state()
                if self._game is not None and result.response and result.response.get("role") == ROLE_SPECTATOR:
                    await self._send_snapshot_or_resync(connection_id, {})
            return
        if msg_type == "ready":
            result = apply_ready(self._state, connection_id, payload.get("ready", False))
            self._state = result.state
            await self._send_control(
                connection_id,
                "ready",
                result.response or {"ok": result.ok, "errors": list(result.errors)},
            )
            if result.ok:
                await self._broadcast_lobby_state()
                await self._maybe_start_game()
            return
        if msg_type == "army_submit":
            await self._handle_army_submit(connection_id, payload)
            return
        if msg_type == "lobby_state":
            await self._send_control(connection_id, "lobby_state", self._state.to_payload())
            return
        if msg_type == "disconnect":
            await self._send_control(connection_id, "disconnect", {"ok": True})
            return
        await self._send_control(connection_id, msg_type, {"ok": False, "errors": ["Unhandled control message."]})

    async def _handle_army_submit(self, connection_id: str, payload: dict) -> None:
        connection = self._state.connections.get(connection_id)
        if connection is None:
            await self._send_control(connection_id, "army_submit", {"ok": False, "errors": ["Unknown connection."]})
            return
        if connection.role not in PLAYER_SLOTS:
            await self._send_control(connection_id, "army_submit", {"ok": False, "errors": ["Not a player."]})
            return
        list_name = payload.get("list_name", "army_list")
        list_text = payload.get("list_text", "")
        if not list_text:
            await self._send_control(connection_id, "army_submit", {"ok": False, "errors": ["list_text required."]})
            return

        try:
            army = parse_army_list_text(str(list_text), self._waha_helper, list_name=str(list_name))
            army.validate()
            army_state = ArmyState(status="validated", list_name=str(list_name), army=army)
            self._state = apply_army_state(self._state, connection.role, army_state)
            await self._send_control(connection_id, "army_submit", {"ok": True, "status": "validated"})
        except (ArmyValidationError, ValueError) as exc:
            army_state = ArmyState(status="invalid", list_name=str(list_name), error=str(exc))
            self._state = apply_army_state(self._state, connection.role, army_state)
            await self._send_control(
                connection_id,
                "army_submit",
                {"ok": False, "status": "invalid", "errors": [str(exc)]},
            )
        await self._broadcast_lobby_state()
        await self._maybe_start_game()

    async def _maybe_start_game(self) -> None:
        if self._game is not None:
            return
        if not is_ready_to_start(self._state):
            return
        armies = {}
        for slot in PLAYER_SLOTS:
            slot_state = self._state.players.get(slot)
            if slot_state is None or slot_state.army.army is None:
                return
            armies[slot] = slot_state.army.army
        self._state = mark_started(self._state)
        self._game = self._build_game(armies["player1"], armies["player2"])
        await self._broadcast_lobby_state()
        await self._send_control("all", "start_game", {"ok": True, "session_id": self._state.session_id})
        await self._broadcast_snapshot()

    def _build_game(self, army1, army2) -> Game:
        player1 = Player("Player 1", control=PlayerControl.REMOTE, army=army1)
        player2 = Player("Player 2", control=PlayerControl.REMOTE, army=army2)
        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, [player1, player2])
        game.map = Map(*game.get_battlefield_size())
        self._player_ids = {
            "player1": player1.id,
            "player2": player2.id,
        }
        game.rebuild_entity_registry()
        event_log = getattr(game, "event_log", None)
        if event_log is None:
            game.event_log = DeterministicEventLog()
            game.event_log.attach(game)
        return game

    async def _handle_game_event(self, connection_id: str, message: dict) -> None:
        if self._game is None:
            await self._send_error(connection_id, "Game not started.")
            return
        parsed = parse_message(message)
        if isinstance(parsed, CommandMessage):
            await self._handle_command(connection_id, parsed)
            return
        await self._send_error(connection_id, "Unexpected game message.")

    async def _handle_command(self, connection_id: str, command_msg: CommandMessage) -> None:
        connection = self._state.connections.get(connection_id)
        if connection is None or connection.role not in PLAYER_SLOTS:
            await self._send_error(connection_id, "Commands are only allowed for players.")
            return
        expected_player_id = self._player_ids.get(connection.role)
        if expected_player_id is None:
            await self._send_error(connection_id, "Player slot not initialized.")
            return
        if command_msg.command.player_id != expected_player_id:
            await self._send_error(connection_id, "Command player_id mismatch.")
            return
        results = handle_command_message(self._game, command_msg, require_client_sync=True)
        for result in results:
            if isinstance(result, EventMessage):
                await self._broadcast_game_message(result)
            elif isinstance(result, ResyncMessage):
                await self._send_game_message(connection_id, result)
            elif isinstance(result, ErrorMessage):
                await self._send_game_message(connection_id, result)

    async def _send_snapshot_or_resync(self, connection_id: str, payload: dict) -> None:
        if self._game is None:
            return
        last_event_id = payload.get("last_event_id")
        if last_event_id is not None:
            msg = build_resync_message(self._game, since_event_id=int(last_event_id))
            await self._send_game_message(connection_id, msg)
            return
        await self._send_game_message(connection_id, build_snapshot_message(self._game))

    async def _broadcast_snapshot(self) -> None:
        if self._game is None:
            return
        msg = build_snapshot_message(self._game)
        await self._broadcast_game_message(msg)

    async def _send_control(self, connection_id: str, msg_type: str, payload: dict) -> None:
        message = build_control_message(msg_type, payload)
        if connection_id == "all":
            await self.transport.broadcast(message)
            return
        await self.transport.send(connection_id, message)

    async def _broadcast_lobby_state(self) -> None:
        await self._send_control("all", "lobby_state", self._state.to_payload())

    async def _send_error(self, connection_id: str, message: str) -> None:
        await self._send_game_message(connection_id, ErrorMessage(errors=[message], context={"scope": "server"}))

    async def _send_game_message(self, connection_id: str, message: Any) -> None:
        await self.transport.send(connection_id, message)

    async def _broadcast_game_message(self, message: Any) -> None:
        await self.transport.broadcast(message)
