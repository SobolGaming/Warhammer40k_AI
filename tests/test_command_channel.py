import asyncio

import pytest

from warhammer40k_ai.engine.command_channel import InProcessCommandChannel, NetworkCommandChannel


class _FakeTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []
        self.broadcasts: list[object] = []

    async def send(self, target_id: str, message: object) -> None:
        self.sent.append((target_id, message))

    async def broadcast(self, message: object) -> None:
        self.broadcasts.append(message)


def test_network_command_channel_delegates_to_transport() -> None:
    async def run() -> None:
        transport = _FakeTransport()
        channel = NetworkCommandChannel(transport)

        await channel.send("p1", {"x": 1})
        await channel.broadcast({"y": 2})

        assert transport.sent == [("p1", {"x": 1})]
        assert transport.broadcasts == [{"y": 2}]

    asyncio.run(run())


def test_inprocess_command_channel_routes_send_and_broadcast() -> None:
    async def run() -> None:
        channel = InProcessCommandChannel()
        received_a: list[object] = []
        received_b: list[object] = []

        async def _a(message: object) -> None:
            received_a.append(message)

        def _b(message: object) -> None:
            received_b.append(message)

        channel.subscribe("a", _a)
        channel.subscribe("b", _b)

        await channel.send("a", {"kind": "one"})
        await channel.broadcast({"kind": "all"})

        assert received_a == [{"kind": "one"}, {"kind": "all"}]
        assert received_b == [{"kind": "all"}]

    asyncio.run(run())


def test_inprocess_command_channel_rejects_duplicate_subscriber_ids() -> None:
    channel = InProcessCommandChannel()
    channel.subscribe("a", lambda _message: None)

    with pytest.raises(ValueError):
        channel.subscribe("a", lambda _message: None)


def test_inprocess_command_channel_raises_for_unknown_target() -> None:
    async def run() -> None:
        channel = InProcessCommandChannel()
        with pytest.raises(KeyError):
            await channel.send("missing", {"kind": "x"})

    asyncio.run(run())
