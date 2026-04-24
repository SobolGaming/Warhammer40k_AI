import asyncio

import pytest

from warhammer40k_ai.network.messages import PROTOCOL_VERSION, SnapshotMessage
from warhammer40k_ai.network.client import NetworkClient
from warhammer40k_ai.network.transport import (
    CONTROL_MESSAGE_TYPES,
    TransportEvent,
    TransportClient,
    TransportServer,
    decode_message,
    encode_message,
    validate_message,
)
from warhammer40k_ai.version import APP_VERSION


def test_transport_encode_decode_roundtrip():
    message = {
        "type": "hello",
        "protocol_version": PROTOCOL_VERSION,
        "payload": {"display_name": "Test", "app_version": APP_VERSION},
    }
    assert "hello" in CONTROL_MESSAGE_TYPES
    encoded = encode_message(message)
    decoded = decode_message(encoded)
    assert decoded == message
    category, msg_type = validate_message(decoded)
    assert category == "control"
    assert msg_type == "hello"


def test_transport_validates_game_message():
    msg = SnapshotMessage(snapshot={"schema_version": 1}).to_dict()
    encoded = encode_message(msg)
    decoded = decode_message(encoded)
    category, msg_type = validate_message(decoded)
    assert category == "game"
    assert msg_type == "snapshot"


def test_transport_server_client_roundtrip():
    async def run_roundtrip():
        server = TransportServer(host="127.0.0.1", port=0, ssl_context=None)
        await server.start()
        client = TransportClient(uri=f"ws://127.0.0.1:{server.port}", ssl_context=None)
        await client.connect()

        await client.send(
            {
                "type": "hello",
                "protocol_version": PROTOCOL_VERSION,
                "payload": {"display_name": "Client", "app_version": APP_VERSION},
            }
        )

        inbound = await server.next_message(timeout=2.0)
        assert inbound.message_type == "hello"
        assert inbound.category == "control"

        await server.send(
            inbound.connection_id,
            {
                "type": "error",
                "protocol_version": PROTOCOL_VERSION,
                "payload": {"errors": ["ok"], "context": {"scope": "test"}},
            },
        )

        response = await client.next_message(timeout=2.0)
        assert response.message_type == "error"
        assert response.category == "game"

        await client.disconnect()
        await server.stop()

    asyncio.run(run_roundtrip())


def test_transport_client_try_next_message():
    client = TransportClient(uri="ws://example", ssl_context=None)
    event = TransportEvent(
        connection_id="client",
        category="control",
        message_type="hello",
        message={"type": "hello", "protocol_version": PROTOCOL_VERSION, "payload": {"display_name": "Test"}},
    )
    client._incoming.put_nowait(event)
    assert client.try_next_message() == event
    assert client.try_next_message() is None


def test_network_client_wait_for_control_times_out_when_server_is_silent():
    async def run_timeout():
        client = NetworkClient(uri="ws://example", response_timeout=0.01)
        with pytest.raises(asyncio.TimeoutError):
            await client.wait_for_control("hello")

    asyncio.run(run_timeout())


def test_network_client_wait_for_control_times_out_on_unexpected_control_response():
    async def run_timeout():
        client = NetworkClient(uri="ws://example", response_timeout=0.01)
        client._pending_messages.append(
            TransportEvent(
                connection_id="client",
                category="control",
                message_type="auth",
                message={"type": "auth", "protocol_version": PROTOCOL_VERSION, "payload": {"ok": False}},
            )
        )
        with pytest.raises(asyncio.TimeoutError):
            await client.wait_for_control("hello")

    asyncio.run(run_timeout())
