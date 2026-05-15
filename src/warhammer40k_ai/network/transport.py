from __future__ import annotations

import asyncio
import json
import ssl
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Tuple

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from ..utility.profiling_sections import profile_section, record_value
from .messages import ErrorMessage, PROTOCOL_VERSION, parse_message, _ensure_jsonable
from .debug import log_network

GAME_MESSAGE_TYPES = {"snapshot", "command", "event", "error", "resync"}
CONTROL_MESSAGE_TYPES = {
    "hello",
    "auth",
    "lobby_state",
    "role_select",
    "army_submit",
    "ready",
    "start_game",
    "disconnect",
}


@dataclass(frozen=True)
class TransportEvent:
    connection_id: str
    category: str
    message_type: str
    message: dict


@dataclass(frozen=True)
class ConnectionEvent:
    connection_id: str
    event: str
    remote: Optional[str] = None


def _coerce_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        return raw.decode("utf-8")
    raise ValueError("WebSocket payload must be text.")


def normalize_message(message: Any) -> dict:
    if hasattr(message, "to_dict"):
        message = message.to_dict()
    if not isinstance(message, dict):
        raise ValueError("Message must be a dict or expose to_dict().")
    return message


def _is_closed(connection: Any) -> bool:
    closed = getattr(connection, "closed", None)
    if closed is not None:
        return bool(closed)
    close_code = getattr(connection, "close_code", None)
    if close_code is not None:
        return True
    return False


def decode_message(raw: Any) -> dict:
    text = _coerce_text(raw)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Message must decode to a dict.")
    return payload


def encode_message(message: Any, *, validate: bool = True) -> str:
    with profile_section("network.encode_message"):
        data = normalize_message(message)
        if validate:
            validate_message(data)
        payload = json.dumps(data, separators=(",", ":"), ensure_ascii=True)
        record_value("network.encode_message.bytes", len(payload))
        return payload


def _validate_control_message(data: dict) -> str:
    if not isinstance(data, dict):
        raise ValueError("Message must be a dict.")
    msg_type = data.get("type")
    if msg_type not in CONTROL_MESSAGE_TYPES:
        raise ValueError(f"Unknown control message type: {msg_type}.")
    version = data.get("protocol_version")
    if version is None:
        raise ValueError("Message missing protocol_version.")
    if int(version) != PROTOCOL_VERSION:
        raise ValueError(f"Unsupported protocol version: {version}.")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Control message payload must be a dict.")
    _ensure_jsonable(payload, "control.payload")
    return msg_type


def validate_message(data: dict, *, allow_control: bool = True, allow_game: bool = True) -> Tuple[str, str]:
    if not isinstance(data, dict):
        raise ValueError("Message must be a dict.")
    msg_type = data.get("type")
    if allow_game and msg_type in GAME_MESSAGE_TYPES:
        parse_message(data)
        return "game", str(msg_type)
    if allow_control:
        control_type = _validate_control_message(data)
        return "control", control_type
    raise ValueError(f"Unknown message type: {msg_type}.")


def build_server_ssl_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    if not cert_path or not key_path:
        raise ValueError("Server TLS requires cert and key paths.")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return context


def build_client_ssl_context(*, ca_cert: Optional[str], insecure: bool) -> ssl.SSLContext:
    if insecure and ca_cert:
        raise ValueError("Cannot combine --ca-cert with --insecure.")
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    if insecure:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    if ca_cert:
        context.load_verify_locations(cafile=ca_cert)
    return context


class TransportServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        ssl_context: Optional[ssl.SSLContext],
        ping_interval: float = 20.0,
        ping_timeout: float = 20.0,
        max_message_size: int = 1_000_000,
    ) -> None:
        self.host = host
        self.port = int(port)
        self._ssl_context = ssl_context
        self._ping_interval = float(ping_interval)
        self._ping_timeout = float(ping_timeout)
        self._max_message_size = int(max_message_size)
        self._server: Optional[websockets.server.Serve] = None
        self._connections: dict[str, Any] = {}
        self._incoming: asyncio.Queue[TransportEvent] = asyncio.Queue()
        self._connection_events: asyncio.Queue[ConnectionEvent] = asyncio.Queue()

    async def start(self) -> None:
        if self._server is not None:
            raise RuntimeError("TransportServer already started.")
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            ssl=self._ssl_context,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
            max_size=self._max_message_size,
        )
        if self._server.sockets:
            self.port = int(self._server.sockets[0].getsockname()[1])

    async def stop(self) -> None:
        if self._server is None:
            return
        await self._close_connections()
        self._server.close()
        await self._server.wait_closed()
        self._server = None

    async def _close_connections(self) -> None:
        for ws in list(self._connections.values()):
            if _is_closed(ws):
                continue
            await ws.close(code=1001)

    async def send(self, connection_id: str, message: Any) -> None:
        ws = self._connections.get(connection_id)
        if ws is None:
            raise ValueError(f"Unknown connection_id: {connection_id}.")
        if _is_closed(ws):
            raise RuntimeError(f"Connection {connection_id} is closed.")
        payload = encode_message(message)
        try:
            await ws.send(payload)
        except ConnectionClosed:
            self._connections.pop(connection_id, None)

    async def broadcast(self, message: Any) -> None:
        payload = encode_message(message)
        for connection_id, ws in list(self._connections.items()):
            if _is_closed(ws):
                continue
            try:
                await ws.send(payload)
            except ConnectionClosed:
                self._connections.pop(connection_id, None)

    async def next_message(self, *, timeout: Optional[float] = None) -> TransportEvent:
        if timeout is None:
            return await self._incoming.get()
        return await asyncio.wait_for(self._incoming.get(), timeout=timeout)

    async def next_connection_event(self, *, timeout: Optional[float] = None) -> ConnectionEvent:
        if timeout is None:
            return await self._connection_events.get()
        return await asyncio.wait_for(self._connection_events.get(), timeout=timeout)

    async def _handler(self, websocket: WebSocketServerProtocol) -> None:
        connection_id = uuid.uuid4().hex
        self._connections[connection_id] = websocket
        remote = None
        if websocket.remote_address:
            remote = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        await self._connection_events.put(
            ConnectionEvent(connection_id=connection_id, event="connected", remote=remote)
        )
        try:
            async for raw in websocket:
                try:
                    data = decode_message(raw)
                    category, msg_type = validate_message(data)
                except ValueError as exc:
                    await self._send_transport_error(websocket, str(exc))
                    continue
                await self._incoming.put(
                    TransportEvent(
                        connection_id=connection_id,
                        category=category,
                        message_type=msg_type,
                        message=data,
                    )
                )
        except ConnectionClosed:
            pass
        finally:
            self._connections.pop(connection_id, None)
            await self._connection_events.put(
                ConnectionEvent(connection_id=connection_id, event="disconnected", remote=remote)
            )

    async def _send_transport_error(self, websocket: WebSocketServerProtocol, detail: str) -> None:
        error = ErrorMessage(errors=[detail], context={"scope": "transport"}).to_dict()
        payload = encode_message(error)
        await websocket.send(payload)


class TransportClient:
    def __init__(
        self,
        *,
        uri: str,
        ssl_context: Optional[ssl.SSLContext],
        ping_interval: float = 20.0,
        ping_timeout: float = 20.0,
        max_message_size: int = 1_000_000,
        reconnect_delay: float = 3.0,
        max_reconnect_attempts: Optional[int] = None,
        on_reconnect: Optional[callable] = None,
    ) -> None:
        self.uri = uri
        self._ssl_context = ssl_context
        self._ping_interval = float(ping_interval)
        self._ping_timeout = float(ping_timeout)
        self._max_message_size = int(max_message_size)
        self._reconnect_delay = float(reconnect_delay)
        self._max_reconnect_attempts = max_reconnect_attempts
        self._on_reconnect = on_reconnect
        self._incoming: asyncio.Queue[TransportEvent] = asyncio.Queue()
        self._connection_events: asyncio.Queue[ConnectionEvent] = asyncio.Queue()
        self._websocket: Optional[Any] = None
        self._receiver_task: Optional[asyncio.Task] = None
        self._closing = False

    async def connect(self) -> None:
        if self._websocket is not None:
            raise RuntimeError("TransportClient already connected.")
        self._websocket = await websockets.connect(
            self.uri,
            ssl=self._ssl_context,
            ping_interval=self._ping_interval,
            ping_timeout=self._ping_timeout,
            max_size=self._max_message_size,
        )
        await self._connection_events.put(ConnectionEvent(connection_id="client", event="connected"))
        self._receiver_task = asyncio.create_task(self._receive_loop())

    async def disconnect(self) -> None:
        if self._websocket is None:
            return
        if not _is_closed(self._websocket):
            await self._websocket.close(code=1000)
        if self._receiver_task is not None:
            await self._receiver_task
        self._websocket = None
        self._receiver_task = None

    async def close(self) -> None:
        self._closing = True
        await self.disconnect()

    async def run_with_reconnect(self) -> None:
        attempts = 0
        while not self._closing:
            try:
                await self.connect()
                await self.wait_closed()
                attempts = 0
            except (OSError, WebSocketException) as exc:
                attempts += 1
                if self._on_reconnect is not None:
                    self._on_reconnect(attempts, exc)
                if self._max_reconnect_attempts is not None and attempts >= self._max_reconnect_attempts:
                    raise
                await asyncio.sleep(self._reconnect_delay)
            finally:
                if self._websocket is not None:
                    await self.disconnect()

    async def wait_closed(self) -> None:
        if self._receiver_task is None:
            return
        await self._receiver_task

    async def send(self, message: Any) -> None:
        if self._websocket is None or _is_closed(self._websocket):
            raise RuntimeError("TransportClient is not connected.")
        payload = encode_message(message)
        await self._websocket.send(payload)

    async def next_message(self, *, timeout: Optional[float] = None) -> TransportEvent:
        if timeout is None:
            return await self._incoming.get()
        return await asyncio.wait_for(self._incoming.get(), timeout=timeout)

    def try_next_message(self) -> Optional[TransportEvent]:
        try:
            return self._incoming.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def next_connection_event(self, *, timeout: Optional[float] = None) -> ConnectionEvent:
        if timeout is None:
            return await self._connection_events.get()
        return await asyncio.wait_for(self._connection_events.get(), timeout=timeout)

    async def _receive_loop(self) -> None:
        assert self._websocket is not None
        try:
            async for raw in self._websocket:
                try:
                    data = decode_message(raw)
                    category, msg_type = validate_message(data)
                except ValueError:
                    await self._websocket.close(code=1003)
                    break
                await self._incoming.put(
                    TransportEvent(
                        connection_id="client",
                        category=category,
                        message_type=msg_type,
                        message=data,
                    )
                )
                log_network(
                    "transport.recv",
                    category=category,
                    type=msg_type,
                    queued=self._incoming.qsize(),
                )
        except ConnectionClosed:
            pass
        finally:
            await self._connection_events.put(ConnectionEvent(connection_id="client", event="disconnected"))
