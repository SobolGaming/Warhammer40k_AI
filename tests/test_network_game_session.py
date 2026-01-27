import asyncio
from types import SimpleNamespace

from warhammer40k_ai.network.game_session import NetworkGameSession
from warhammer40k_ai.network.messages import PROTOCOL_VERSION
from warhammer40k_ai.network.transport import TransportEvent


class _FakeClient:
    def __init__(self) -> None:
        self._incoming: asyncio.Queue[TransportEvent] = asyncio.Queue()
        self.handled: list[tuple[str, str]] = []
        self.player_id = None
        self.role = None
        self.session_token = None
        self.event_cursor = SimpleNamespace(last_event_id=0)

    async def next_message(self, *, timeout: float | None = None) -> TransportEvent:
        if timeout == 0.0:
            try:
                return self._incoming.get_nowait()
            except asyncio.QueueEmpty as exc:
                raise asyncio.TimeoutError from exc
        if timeout is None:
            return await self._incoming.get()
        return await asyncio.wait_for(self._incoming.get(), timeout=timeout)

    def handle_message(self, event: TransportEvent) -> None:
        self.handled.append((event.category, event.message_type))


def _lobby_state_event() -> TransportEvent:
    return TransportEvent(
        connection_id="client",
        category="control",
        message_type="lobby_state",
        message={
            "type": "lobby_state",
            "protocol_version": PROTOCOL_VERSION,
            "payload": {"session_id": "s", "started": True},
        },
    )


def test_poll_messages_yields_when_queue_empty() -> None:
    async def run() -> None:
        client = _FakeClient()
        session = NetworkGameSession(client)
        background_ran = {"ran": False}

        async def _enqueue_next_loop() -> None:
            await asyncio.sleep(0)
            background_ran["ran"] = True
            await client._incoming.put(_lobby_state_event())

        task = asyncio.create_task(_enqueue_next_loop())

        # The first poll sees an empty queue. It should still yield once so the
        # background receive task can enqueue work.
        await session.poll_messages()
        assert background_ran["ran"] is True

        # A subsequent poll should then process the enqueued message.
        await session.poll_messages()
        assert ("control", "lobby_state") in client.handled

        await task

    asyncio.run(run())

