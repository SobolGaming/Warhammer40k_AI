from __future__ import annotations

import asyncio
import contextlib
import ssl
from typing import Any, Dict, Optional

from ..engine.game import Battlefield, BattlefieldSize, Game
from ..engine.authoritative_session_driver import AuthoritativeSessionDriver
from ..engine.command_channel import NetworkCommandChannel
from ..battlefield.map import Map
from ..engine.event_log import DeterministicEventLog
from ..engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_REQUEST_DECISION,
    CMD_RESOLVE_DECISION,
)
from ..engine.commands import GameCommand
from ..engine.command_dispatcher import CommandResult
from ..engine.decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_SHADOW_ASSIGNMENT,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_CHOOSE_PLAGUE,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_DICE_REROLL,
)
from ..engine.decisions import DecisionOption, DecisionRequest
from ..engine.decision_requests import (
    build_leader_attachment_requests,
    build_patrol_squad_requests,
    build_player_color_selection_requests,
    build_risen_rubricae_requests,
    build_shadow_assignment_requests,
    build_support_artillery_attachment_requests,
    build_hover_mode_requests,
    build_transport_assignment_requests,
    build_reserves_allocation_request,
)
from ..engine.mission_selection import iter_random_mission_options
from ..roster.player import Player, PlayerControl
from ..roster.army import ArmyValidationError, parse_army_list_text
from ..utility.dice import get_dice_roll
from ..utility.entity_ids import get_entity_id
from ..utility.game_context import game_context, roll_context
from ..waha_helper import WahaHelper
from ..version import get_app_version
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


_SERVER_SNAPSHOT_SYNC_COMMANDS = {
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_RESOLVE_DECISION,
}


def _server_command_requires_snapshot_sync(command: GameCommand | None) -> bool:
    if command is None:
        return False
    return str(getattr(command, "kind", "") or "") in _SERVER_SNAPSHOT_SYNC_COMMANDS


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
        self._game_channel = NetworkCommandChannel(self.transport)
        self._state = new_lobby_state(join_code=join_code)
        self._game: Optional[Game] = None
        self._player_ids: Dict[str, str] = {}
        self._waha_helper = WahaHelper()
        self._setup_task: Optional[asyncio.Task] = None
        self._formation_buffering = False
        self._suppress_decision_broadcast: set[str] = set()
        self._formation_decision_types = {
            DECISION_ATTACH_LEADER,
            DECISION_ATTACH_SUPPORT_ARTILLERY,
            DECISION_ASSIGN_TRANSPORT,
            DECISION_SHADOW_ASSIGNMENT,
            DECISION_DECLARE_RESERVES,
            DECISION_CHOOSE_PLAGUE,
            DECISION_CHOOSE_PLAYER_COLOR,
        }
        self._session_driver = AuthoritativeSessionDriver(
            get_game=lambda: self._game,
            is_running=lambda: self._running,
            apply_command=self._apply_server_command_default,
            apply_command_with_broadcast=self._apply_server_command_with_broadcast,
            choose_random_mission=self._choose_random_mission,
            queue_formation_decisions=self._queue_formation_decisions,
            pending_formation_decisions=self._pending_formation_decisions,
            wait_for_formation_decisions=self._wait_for_formation_decisions,
            broadcast_resync_all=self._broadcast_resync_all,
            set_formation_buffering=self._set_formation_buffering,
            should_wait_for_formation_decisions=lambda: True,
            skip_muster_phase=True,
        )

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
        if self._setup_task is not None and not self._setup_task.done():
            self._setup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._setup_task
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
            client_version = str(payload.get("app_version") or "").strip()
            server_version = get_app_version()
            version_ok = bool(client_version) and client_version == server_version
            self._state = apply_hello(
                self._state,
                connection_id,
                display_name,
                client_version=client_version or None,
                version_ok=version_ok,
            )
            response: dict[str, Any] = {
                "ok": bool(version_ok),
                "server": "warhammer40k_ai",
                "server_version": server_version,
                "client_version": client_version or None,
            }
            if not client_version:
                response["errors"] = ["app_version is required for handshake."]
                response["ok"] = False
            elif not version_ok:
                response["errors"] = [
                    f"Version mismatch. Server={server_version} Client={client_version}."
                ]
                response["ok"] = False
            await self._send_control(connection_id, "hello", response)
            await self._broadcast_lobby_state()
            return
        if not self._connection_version_ok(connection_id):
            await self._send_version_negotiation_required(connection_id, msg_type)
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

    def _connection_version_ok(self, connection_id: str) -> bool:
        connection = self._state.connections.get(connection_id)
        return bool(connection is not None and connection.hello_received and connection.version_ok)

    async def _send_version_negotiation_required(self, connection_id: str, msg_type: str) -> None:
        await self._send_control(
            connection_id,
            msg_type,
            {
                "ok": False,
                "code": "version_negotiation_required",
                "errors": ["version_negotiation_required"],
            },
        )

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
        await self._start_setup_driver()

    async def _start_setup_driver(self) -> None:
        if self._setup_task is not None and not self._setup_task.done():
            return
        self._setup_task = asyncio.create_task(self._run_setup_sequence())

    async def _run_setup_sequence(self) -> None:
        await self._session_driver.run_setup_sequence()

    def _set_formation_buffering(self, value: bool) -> None:
        self._formation_buffering = bool(value)

    async def _apply_server_command_default(self, command: GameCommand):
        return await self._apply_server_command(command, broadcast=True)

    async def _apply_server_command_with_broadcast(self, command: GameCommand, broadcast: bool):
        return await self._apply_server_command(command, broadcast=broadcast)

    def _choose_random_mission(self, game: Game) -> tuple[dict, int]:
        combos = iter_random_mission_options(game)
        if not combos:
            raise RuntimeError("No mission-pack entries available for random selection.")
        with game_context(game), roll_context("mission_selection"):
            combo_index = max(1, int(get_dice_roll(len(combos)))) - 1
            combo_index = min(combo_index, len(combos) - 1)
            combo = combos[combo_index]
            layouts = list(combo.get("layouts", []) or [])
            if not layouts:
                raise RuntimeError("Selected mission-pack entry has no layouts.")
            layout_index = max(1, int(get_dice_roll(len(layouts)))) - 1
            layout_index = min(layout_index, len(layouts) - 1)
            layout = layouts[layout_index]
        return combo, int(layout)

    def _attach_game_event_handlers(self, game: Game) -> None:
        event_system = getattr(game, "event_system", None)
        if event_system is None:
            return
        try:
            event_system.subscribe("decision_requested", self._on_decision_requested)
        except Exception:
            pass

    def _on_decision_requested(self, request=None, **_kwargs) -> None:
        if request is None:
            return
        decision_id = getattr(request, "decision_id", None)
        if decision_id and decision_id in self._suppress_decision_broadcast:
            self._suppress_decision_broadcast.discard(decision_id)
            return
        if not self._running:
            return
        try:
            asyncio.create_task(self._broadcast_decision_request(request))
        except Exception:
            pass

    async def _broadcast_decision_request(self, request: DecisionRequest) -> None:
        if request is None or self._game is None:
            return
        payload = {"decision": request.to_dict()}
        cmd = GameCommand.create(CMD_REQUEST_DECISION, player_id=request.player_id, payload=payload)
        await self._broadcast_game_message(CommandMessage(command=cmd))

    async def _apply_server_command(self, command: GameCommand, *, broadcast: bool = True):
        if self._game is None:
            return []
        roll_context = None
        if command is not None and getattr(command, "kind", None) == CMD_RESOLVE_DECISION:
            payload = getattr(command, "payload", {}) or {}
            decision_id = payload.get("decision_id")
            if decision_id:
                queue = getattr(self._game, "decision_queue", None)
                req = queue.get(str(decision_id)) if queue is not None and hasattr(queue, "get") else None
                if req is not None and getattr(req, "decision_type", None) in (
                    DECISION_REQUEST_DICE_ROLL,
                    DECISION_SELECT_DICE_REROLL,
                ):
                    roll_context = {"decision_id": str(decision_id), "roll_id": req.context.get("roll_id")}

        message = CommandMessage(command=command, client_last_event_id=None)
        results = handle_command_message(self._game, message, require_client_sync=False)
        had_resync = any(isinstance(result, ResyncMessage) for result in results)
        had_error = any(isinstance(result, ErrorMessage) for result in results)
        broadcast_command = command
        if roll_context and self._game is not None:
            roll_id = roll_context.get("roll_id")
            try:
                mgr = getattr(self._game, "roll_manager", None)
                if mgr is not None and roll_id is not None:
                    roll_results = mgr.export_roll_results(int(roll_id))
                    payload = dict(getattr(command, "payload", {}) or {})
                    rp = dict(payload.get("result_payload", {}) or {})
                    rp["roll_results"] = roll_results
                    payload["result_payload"] = rp
                    broadcast_command = GameCommand(
                        command_id=command.command_id,
                        kind=command.kind,
                        player_id=command.player_id,
                        payload=payload,
                        metadata=command.metadata,
                        created_at=command.created_at,
                    )
            except Exception:
                broadcast_command = command
        snapshot_sync = bool(broadcast and _server_command_requires_snapshot_sync(command))
        if broadcast and not had_resync and not had_error:
            if snapshot_sync:
                await self._broadcast_snapshot()
            else:
                await self._broadcast_game_message(CommandMessage(command=broadcast_command))
        for result in results:
            if isinstance(result, EventMessage):
                if broadcast and not snapshot_sync:
                    await self._broadcast_game_message(result)
            elif isinstance(result, ResyncMessage):
                await self._broadcast_game_message(result)
            elif isinstance(result, ErrorMessage):
                await self._broadcast_game_message(result)
        return results

    def _should_buffer_command(self, command: GameCommand) -> bool:
        if not self._formation_buffering:
            return False
        if command is None or getattr(command, "kind", None) != CMD_RESOLVE_DECISION:
            return False
        payload = getattr(command, "payload", {}) or {}
        decision_id = payload.get("decision_id")
        if not decision_id or self._game is None:
            return False
        queue = getattr(self._game, "decision_queue", None)
        if queue is None or not hasattr(queue, "get"):
            return False
        request = queue.get(str(decision_id))
        if request is None:
            return False
        return self._is_formation_decision(request)

    def _pending_formation_decisions(self) -> list[DecisionRequest]:
        if self._game is None:
            return []
        queue = getattr(self._game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return []
        return [req for req in list(queue.list() or []) if self._is_formation_decision(req)]

    async def _queue_formation_decisions(self) -> list[DecisionRequest]:
        if self._game is None:
            return []
        game = self._game
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return []

        pending_attach = self._pending_by_context(DECISION_ATTACH_LEADER, "leader_id")
        pending_support = self._pending_by_context(DECISION_ATTACH_SUPPORT_ARTILLERY, "support_unit_id")
        pending_transport = self._pending_by_context(DECISION_ASSIGN_TRANSPORT, "unit_id")
        pending_shadow = self._pending_by_context(DECISION_SHADOW_ASSIGNMENT, "unit_id")
        pending_reserves = self._pending_by_context(DECISION_DECLARE_RESERVES, "army_id")
        pending_plague = self._pending_by_context(DECISION_CHOOSE_PLAGUE, "army_id")
        pending_player_color = self._pending_by_context(DECISION_CHOOSE_PLAYER_COLOR, "player_id")
        pending_hover = self._pending_hover_by_unit()
        pending_patrol = self._pending_patrol_squad_by_unit()
        pending_risen = self._pending_risen_rubricae_by_source()

        created: list[DecisionRequest] = []

        for player in list(getattr(game, "players", []) or []):
            if player is None:
                continue
            color_requests = build_player_color_selection_requests(game, [player], queue_requests=False)
            for req in color_requests:
                player_id = str(getattr(req, "context", {}).get("player_id", "") or "")
                if player_id and player_id in pending_player_color:
                    continue
                await self._send_decision_request(req)
                created.append(req)
                if player_id:
                    pending_player_color[player_id] = req

            army = player.get_army()
            if army is None:
                continue
            units = list(getattr(army, "units", []) or [])

            hover_requests = build_hover_mode_requests(game, units, queue_requests=False)
            for req in hover_requests:
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_hover:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            patrol_requests = build_patrol_squad_requests(game, units, queue_requests=False)
            for req in patrol_requests:
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_patrol:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            shadow_requests = build_shadow_assignment_requests(game, units, queue_requests=False)
            for req in shadow_requests:
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_shadow:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            leader_requests = build_leader_attachment_requests(game, units, queue_requests=False)
            for req in leader_requests:
                leader_id = str(getattr(req, "context", {}).get("leader_id", "") or "")
                if leader_id and leader_id in pending_attach:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            risen_requests = build_risen_rubricae_requests(game, units, queue_requests=False)
            for req in risen_requests:
                source_id = str(getattr(req, "context", {}).get("source_unit_id", "") or "")
                if source_id and source_id in pending_risen:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            support_requests = build_support_artillery_attachment_requests(game, units, queue_requests=False)
            for req in support_requests:
                support_id = str(getattr(req, "context", {}).get("support_unit_id", "") or "")
                if support_id and support_id in pending_support:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            transport_requests = build_transport_assignment_requests(game, units, queue_requests=False)
            for req in transport_requests:
                unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
                if unit_id and unit_id in pending_transport:
                    continue
                await self._send_decision_request(req)
                created.append(req)

            army_id = get_entity_id(army)
            reserves_request = build_reserves_allocation_request(game, army, queue_requests=False)
            if reserves_request is not None:
                if army_id and army_id in pending_reserves:
                    pass
                else:
                    await self._send_decision_request(reserves_request)
                    created.append(reserves_request)

            plague_request = self._build_plague_request(player, army, pending_plague)
            if plague_request is not None:
                await self._send_decision_request(plague_request)
                created.append(plague_request)

        return created

    def _pending_by_context(self, decision_type: str, context_key: str) -> dict[str, DecisionRequest]:
        pending: dict[str, DecisionRequest] = {}
        if self._game is None:
            return pending
        queue = getattr(self._game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return pending
        for req in list(queue.list() or []):
            if getattr(req, "decision_type", None) != decision_type:
                continue
            ctx_val = str(getattr(req, "context", {}).get(context_key, "") or "")
            if ctx_val:
                pending[ctx_val] = req
        return pending

    def _pending_hover_by_unit(self) -> dict[str, DecisionRequest]:
        pending: dict[str, DecisionRequest] = {}
        if self._game is None:
            return pending
        queue = getattr(self._game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return pending
        for req in list(queue.list() or []):
            if not self._is_hover_mode_request(req):
                continue
            unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
            if unit_id:
                pending[unit_id] = req
        return pending

    def _pending_patrol_squad_by_unit(self) -> dict[str, DecisionRequest]:
        pending: dict[str, DecisionRequest] = {}
        if self._game is None:
            return pending
        queue = getattr(self._game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return pending
        for req in list(queue.list() or []):
            if not self._is_patrol_squad_request(req):
                continue
            unit_id = str(getattr(req, "context", {}).get("unit_id", "") or "")
            if unit_id:
                pending[unit_id] = req
        return pending

    def _pending_risen_rubricae_by_source(self) -> dict[str, DecisionRequest]:
        pending: dict[str, DecisionRequest] = {}
        if self._game is None:
            return pending
        queue = getattr(self._game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return pending
        for req in list(queue.list() or []):
            if not self._is_risen_rubricae_request(req):
                continue
            source_id = str(getattr(req, "context", {}).get("source_unit_id", "") or "")
            if source_id:
                pending[source_id] = req
        return pending

    def _is_hover_mode_request(self, request: DecisionRequest | None) -> bool:
        if request is None:
            return False
        if getattr(request, "decision_type", None) != DECISION_CONFIRM_YES_NO:
            return False
        ctx = getattr(request, "context", {}) or {}
        return str(ctx.get("ability", "") or "") == "hover_mode"

    def _is_risen_rubricae_request(self, request: DecisionRequest | None) -> bool:
        if request is None:
            return False
        if getattr(request, "decision_type", None) != DECISION_CHOOSE_QUARRY:
            return False
        ctx = dict(getattr(request, "context", {}) or {})
        return str(ctx.get("ability", "") or "") == "risen_rubricae"

    def _is_patrol_squad_request(self, request: DecisionRequest | None) -> bool:
        if request is None:
            return False
        if getattr(request, "decision_type", None) != DECISION_CONFIRM_YES_NO:
            return False
        ctx = getattr(request, "context", {}) or {}
        return str(ctx.get("ability", "") or "") in {"patrol_squad", "combat_squads"}

    def _is_formation_decision(self, request: DecisionRequest | None) -> bool:
        if request is None:
            return False
        if getattr(request, "decision_type", None) in self._formation_decision_types:
            return True
        if self._is_risen_rubricae_request(request):
            return True
        if self._is_hover_mode_request(request):
            return True
        return self._is_patrol_squad_request(request)

    def _build_plague_request(
        self,
        player: Player,
        army: object,
        pending_plague: dict[str, DecisionRequest],
    ) -> Optional[DecisionRequest]:
        army_id = get_entity_id(army)
        if army_id and army_id in pending_plague:
            return None
        mgr = getattr(army, "nurgles_gift", None)
        if mgr is None or not getattr(mgr, "_army_has_gift", lambda: False)():
            return None
        if getattr(mgr, "active_plague_key", None):
            return None
        try:
            from ..rules.nurgles_gift import DEFAULT_PLAGUES
        except Exception:
            return None
        options: list[DecisionOption] = []
        for plague in list(DEFAULT_PLAGUES):
            key = getattr(plague, "key", None)
            if not key:
                continue
            name = getattr(plague, "name", None) or str(plague)
            summary = getattr(plague, "summary", "") or getattr(plague, "effect", "")
            options.append(
                DecisionOption.create(
                    name,
                    payload={"choice_key": str(key), "summary": summary, "army_id": army_id},
                )
            )
        if not options:
            return None
        return DecisionRequest.create(
            DECISION_CHOOSE_PLAGUE,
            "Select Nurgle's Gift plague.",
            player_id=getattr(player, "id", None),
            options=options,
            context={"army_id": army_id},
        )

    async def _send_decision_request(self, request: DecisionRequest) -> None:
        decision_id = getattr(request, "decision_id", None)
        if decision_id:
            self._suppress_decision_broadcast.add(str(decision_id))
        payload = {"decision": request.to_dict()}
        cmd = GameCommand.create(CMD_REQUEST_DECISION, player_id=request.player_id, payload=payload)
        await self._apply_server_command(cmd)

    async def _wait_for_formation_decisions(self, poll_interval: float = 0.25) -> None:
        while self._running and self._game is not None:
            if not self._pending_formation_decisions():
                return
            await asyncio.sleep(poll_interval)

    async def _broadcast_resync_all(self, reason: str | None = None) -> None:
        if self._game is None:
            return
        msg = build_resync_message(self._game, since_event_id=0, reason=reason)
        await self._broadcast_game_message(msg)

    def _build_game(self, army1, army2) -> Game:
        player1 = Player("Player 1", control=PlayerControl.REMOTE, army=army1)
        player2 = Player("Player 2", control=PlayerControl.REMOTE, army=army2)
        battlefield = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(battlefield, [player1, player2])
        try:
            game.auto_resolve_dice_rolls = False
        except Exception:
            pass
        try:
            game.is_authoritative = True
        except Exception:
            pass
        game.set_map(Map(*game.get_battlefield_size()))
        self._player_ids = {
            "player1": player1.id,
            "player2": player2.id,
        }
        game.rebuild_entity_registry()
        event_log = getattr(game, "event_log", None)
        if event_log is None:
            game.event_log = DeterministicEventLog()
            game.event_log.attach(game)
        self._attach_game_event_handlers(game)
        return game

    async def _handle_game_event(self, connection_id: str, message: dict) -> None:
        if not self._connection_version_ok(connection_id):
            await self._send_error(connection_id, "version_negotiation_required")
            return
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
        buffer_command = self._should_buffer_command(command_msg.command)
        results = handle_command_message(self._game, command_msg, require_client_sync=True)
        had_resync = any(isinstance(result, ResyncMessage) for result in results)
        had_error = any(isinstance(result, ErrorMessage) for result in results)
        if not buffer_command and not had_resync and not had_error:
            await self._broadcast_game_message(CommandMessage(command=command_msg.command))
        for result in results:
            if isinstance(result, EventMessage):
                if not buffer_command:
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
            for target_id, connection in list(self._state.connections.items()):
                if connection.version_ok:
                    try:
                        await self.transport.send(target_id, message)
                    except (RuntimeError, ValueError):
                        continue
            return
        await self.transport.send(connection_id, message)

    async def _broadcast_lobby_state(self) -> None:
        await self._send_control("all", "lobby_state", self._state.to_payload())

    async def _send_error(self, connection_id: str, message: str) -> None:
        await self._send_game_message(connection_id, ErrorMessage(errors=[message], context={"scope": "server"}))

    async def _send_game_message(self, connection_id: str, message: Any) -> None:
        await self._game_channel.send(connection_id, message)

    async def _broadcast_game_message(self, message: Any) -> None:
        await self._game_channel.broadcast(message)
