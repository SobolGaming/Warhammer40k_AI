import asyncio
from types import SimpleNamespace

from warhammer40k_ai.engine.command_kinds import CMD_RESOLVE_DECISION
from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
import warhammer40k_ai.network.game_session as game_session_module
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
        queued = {"ran": False}
        loop = asyncio.get_running_loop()

        def _enqueue_next_loop() -> None:
            queued["ran"] = True
            client._incoming.put_nowait(_lobby_state_event())

        loop.call_soon(_enqueue_next_loop)

        # The first poll sees an empty queue. It should still yield once so the
        # background receive task can enqueue work.
        await session.poll_messages()
        assert queued["ran"] is True

        # A subsequent poll should then process the enqueued message.
        await session.poll_messages()
        assert ("control", "lobby_state") in client.handled

    asyncio.run(run())


def test_auto_dice_fallback_uses_shared_controller_when_game_has_no_controller_hub() -> None:
    class _FakeEventSystem:
        def __init__(self) -> None:
            self._handlers: list[tuple[str, object, str | None]] = []

        def subscribe(self, event_name: str, handler, group: str | None = None) -> None:
            self._handlers.append((event_name, handler, group))

        def unsubscribe_group(self, group: str) -> None:
            self._handlers = [entry for entry in self._handlers if entry[2] != group]

        def emit(self, event_name: str, **kwargs) -> None:
            for name, handler, _group in list(self._handlers):
                if name == event_name:
                    handler(**kwargs)

    async def run() -> None:
        client = _FakeClient()
        client.player_id = "p1"
        session = NetworkGameSession(client, allow_commands=True)

        player = SimpleNamespace(id="p1", has_control=lambda: True)
        fake_game = SimpleNamespace(
            auto_resolve_dice_rolls=True,
            event_system=_FakeEventSystem(),
            entity_registry=None,
            players=[player],
        )
        session._set_game(fake_game)

        request = DecisionRequest.create(
            DECISION_REQUEST_DICE_ROLL,
            "Roll now",
            player_id="p1",
            options=[
                DecisionOption.create("Roll", payload={"action_id": "roll"}),
            ],
            context={"roll_id": 1},
        )
        fake_game.event_system.emit("decision_requested", request=request, game=fake_game)

        assert len(session._outgoing) == 1
        queued = session._outgoing[0]
        assert queued.kind == CMD_RESOLVE_DECISION
        assert queued.payload.get("decision_id") == request.decision_id
        assert queued.payload.get("option_id") == request.options[0].option_id

    asyncio.run(run())


def test_snapshot_loaded_network_games_disable_local_dice_auto_resolve(monkeypatch) -> None:
    fake_game = SimpleNamespace(
        auto_resolve_dice_rolls=True,
        event_log=None,
        players=[],
    )

    monkeypatch.setattr(game_session_module, "load_game_snapshot", lambda _snapshot: fake_game)

    client = _FakeClient()
    session = NetworkGameSession(client)

    loaded = session._build_game({"schema_version": 1})

    assert loaded is fake_game
    assert fake_game.auto_resolve_dice_rolls is False
