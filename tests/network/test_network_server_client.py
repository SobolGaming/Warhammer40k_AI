import asyncio
import contextlib
from pathlib import Path

import pytest

from warhammer40k_ai.engine.command_kinds import CMD_NEXT_PHASE, CMD_REQUEST_DECISION
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR
from warhammer40k_ai.engine.phase import SetupPhase
from warhammer40k_ai.network.client import NetworkClient
from warhammer40k_ai.network.game_session import NetworkGameSession
from warhammer40k_ai.network.messages import CommandMessage
from warhammer40k_ai.network.server import NetworkServer
from warhammer40k_ai.version import APP_VERSION

CERT_PATH = Path("tests/fixtures/tls/server.crt")
KEY_PATH = Path("tests/fixtures/tls/server.key")
pytestmark = [pytest.mark.integration, pytest.mark.slow]


async def _wait_for(client: NetworkClient, category: str, message_type: str, timeout: float = 20.0):
    while True:
        event = await client.next_message(timeout=timeout)
        client.handle_message(event)
        if event.category == category and event.message_type == message_type:
            return event


async def _wait_for_player_color_decision_request(client: NetworkClient, timeout: float = 20.0):
    while True:
        event = await client.next_message(timeout=timeout)
        client.handle_message(event)
        if event.category != "game" or event.message_type != "command":
            continue
        command = dict((event.message.get("payload", {}) or {}).get("command", {}) or {})
        if str(command.get("kind", "") or "") != CMD_REQUEST_DECISION:
            continue
        payload = dict(command.get("payload", {}) or {})
        decision = dict(payload.get("decision", {}) or {})
        if str(decision.get("decision_type", "") or "") == DECISION_CHOOSE_PLAYER_COLOR:
            return event


async def _wait_for_session(
    session: NetworkGameSession,
    category: str,
    message_type: str,
    timeout: float = 20.0,
):
    while True:
        event = await session.client.next_message(timeout=timeout)
        await session.handle_message(event)
        if event.category == category and event.message_type == message_type:
            return event


def _session_setup_phase(session: NetworkGameSession):
    game = session.game
    if game is None:
        return None
    get_phase = getattr(game, "get_current_setup_phase", None)
    if callable(get_phase):
        return get_phase()
    return getattr(game, "setup_phase", None)


async def _wait_for_session_setup_phase(
    sessions: list[NetworkGameSession],
    phase: SetupPhase,
    timeout: float = 20.0,
) -> int:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    snapshot_count = 0
    while loop.time() < deadline:
        for session in sessions:
            while True:
                try:
                    event = await session.client.next_message(timeout=0.0)
                except asyncio.TimeoutError:
                    break
                if event.category == "game" and event.message_type == "snapshot":
                    snapshot_count += 1
                await session.handle_message(event)
        if all(_session_setup_phase(session) == phase for session in sessions):
            return snapshot_count
        await asyncio.sleep(0.05)
    phases = [_session_setup_phase(session) for session in sessions]
    raise TimeoutError(f"Timed out waiting for setup phase {phase}; phases={phases}")


def test_network_server_client_flow_tls():
    async def run_flow():
        server = NetworkServer(
            host="127.0.0.1",
            port=0,
            cert_path=str(CERT_PATH),
            key_path=str(KEY_PATH),
        )
        await server.start()
        server_task = asyncio.create_task(server.run())

        uri = f"wss://localhost:{server.transport.port}"
        client1 = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        client2 = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        await client1.connect()
        await client2.connect()

        await client1.send_hello("Alice")
        await client2.send_hello("Bob")
        hello1 = await _wait_for(client1, "control", "hello")
        hello2 = await _wait_for(client2, "control", "hello")
        assert hello1.message.get("payload", {}).get("ok") is True
        assert hello2.message.get("payload", {}).get("ok") is True
        await client1.send_auth()
        await client2.send_auth()
        await _wait_for(client1, "control", "auth")
        await _wait_for(client2, "control", "auth")

        await client1.send_role_select("player1")
        await client2.send_role_select("player2")
        await _wait_for(client1, "control", "role_select")
        await _wait_for(client2, "control", "role_select")

        army1 = Path("army_lists/chaos_test.txt").read_text(encoding="utf-8")
        army2 = Path("army_lists/aeldari_test.txt").read_text(encoding="utf-8")
        await client1.send_army_submit(army1, list_name="chaos_test.txt")
        await client2.send_army_submit(army2, list_name="aeldari_test.txt")
        await _wait_for(client1, "control", "army_submit")
        await _wait_for(client2, "control", "army_submit")

        await client1.send_ready(True)
        await client2.send_ready(True)
        await _wait_for(client1, "control", "ready")
        await _wait_for(client2, "control", "ready")

        await _wait_for(client1, "control", "start_game")
        snapshot1 = await _wait_for(client1, "game", "snapshot")
        snapshot2 = await _wait_for(client2, "game", "snapshot")
        snapshot1_players = list(
            ((snapshot1.message.get("payload", {}) or {}).get("snapshot", {}) or {}).get("players", []) or []
        )
        snapshot2_players = list(
            ((snapshot2.message.get("payload", {}) or {}).get("snapshot", {}) or {}).get("players", []) or []
        )
        assert len(snapshot1_players) == 2
        assert len(snapshot2_players) == 2
        for player_data in snapshot1_players + snapshot2_players:
            state = dict(player_data.get("state", {}) or {})
            rgb = list(state.get("ui_color_rgb", []) or [])
            assert len(rgb) == 3
            assert all(0 <= int(channel) <= 255 for channel in rgb)
        await _wait_for_player_color_decision_request(client1)

        command = GameCommand.create(CMD_NEXT_PHASE, player_id=client1.player_id)
        await client1.send_command(command)
        await _wait_for(client1, "game", "event")

        spectator = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        await spectator.connect()
        await spectator.send_hello("Spec")
        await _wait_for(spectator, "control", "hello")
        await spectator.send_auth()
        await _wait_for(spectator, "control", "auth")
        await spectator.send_role_select("spectator")
        await _wait_for(spectator, "control", "role_select")
        await _wait_for(spectator, "game", "snapshot")

        bad_cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=client1.player_id)
        await spectator.transport.send(CommandMessage(command=bad_cmd, client_last_event_id=0))
        await _wait_for(spectator, "game", "error")

        desync_cmd = GameCommand.create(CMD_NEXT_PHASE, player_id=client1.player_id)
        await client1.transport.send(CommandMessage(command=desync_cmd, client_last_event_id=0))
        await _wait_for(client1, "game", "resync")

        await spectator.close()
        await client1.close()
        await client2.close()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task
        await server.stop()

    asyncio.run(run_flow())


def test_network_game_session_reaches_formation_from_setup_snapshots_tls():
    async def run_flow():
        server = NetworkServer(
            host="127.0.0.1",
            port=0,
            cert_path=str(CERT_PATH),
            key_path=str(KEY_PATH),
        )
        await server.start()
        server_task = asyncio.create_task(server.run())

        uri = f"wss://localhost:{server.transport.port}"
        client1 = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        client2 = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        session1 = NetworkGameSession(client1)
        session2 = NetworkGameSession(client2)
        try:
            await client1.connect()
            await client2.connect()

            await client1.send_hello("Alice")
            await client2.send_hello("Bob")
            await _wait_for_session(session1, "control", "hello")
            await _wait_for_session(session2, "control", "hello")
            await client1.send_auth()
            await client2.send_auth()
            await _wait_for_session(session1, "control", "auth")
            await _wait_for_session(session2, "control", "auth")

            await client1.send_role_select("player1")
            await client2.send_role_select("player2")
            await _wait_for_session(session1, "control", "role_select")
            await _wait_for_session(session2, "control", "role_select")

            army1 = Path("army_lists/chaos_test.txt").read_text(encoding="utf-8")
            army2 = Path("army_lists/aeldari_test.txt").read_text(encoding="utf-8")
            await client1.send_army_submit(army1, list_name="chaos_test.txt")
            await client2.send_army_submit(army2, list_name="aeldari_test.txt")
            await _wait_for_session(session1, "control", "army_submit")
            await _wait_for_session(session2, "control", "army_submit")

            await client1.send_ready(True)
            await client2.send_ready(True)
            await _wait_for_session(session1, "control", "ready")
            await _wait_for_session(session2, "control", "ready")

            await _wait_for_session(session1, "control", "start_game")
            await _wait_for_session(session2, "control", "start_game")
            await _wait_for_session(session1, "game", "snapshot")
            await _wait_for_session(session2, "game", "snapshot")

            snapshot_count = await _wait_for_session_setup_phase(
                [session1, session2],
                SetupPhase.DECLARE_BATTLE_FORMATIONS,
            )

            assert snapshot_count > 0
            assert session1.game is not None
            assert session2.game is not None
            assert session1.game_proxy is not None
            assert session2.game_proxy is not None
            assert client1.player_id
            assert client2.player_id
            assert session1.last_error is None
            assert session2.last_error is None
        finally:
            await client1.close()
            await client2.close()
            server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await server_task
            await server.stop()

    asyncio.run(run_flow())


def test_network_version_mismatch_rejects_auth_tls():
    async def run_flow():
        server = NetworkServer(
            host="127.0.0.1",
            port=0,
            cert_path=str(CERT_PATH),
            key_path=str(KEY_PATH),
        )
        await server.start()
        server_task = asyncio.create_task(server.run())

        uri = f"wss://localhost:{server.transport.port}"
        client = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        await client.connect()

        bad_version = "0.0.0"
        assert bad_version != APP_VERSION
        await client.send_hello("Mismatch", app_version=bad_version)
        hello_event = await _wait_for(client, "control", "hello")
        assert hello_event.message.get("payload", {}).get("ok") is False

        await client.send_auth()
        auth_event = await _wait_for(client, "control", "auth")
        assert auth_event.message.get("payload", {}).get("ok") is False

        await client.close()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task
        await server.stop()

    asyncio.run(run_flow())


def test_network_rejects_control_before_successful_hello_tls():
    async def run_flow():
        server = NetworkServer(
            host="127.0.0.1",
            port=0,
            cert_path=str(CERT_PATH),
            key_path=str(KEY_PATH),
        )
        await server.start()
        server_task = asyncio.create_task(server.run())

        uri = f"wss://localhost:{server.transport.port}"
        client = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        await client.connect()

        await client.send_auth()
        auth_event = await _wait_for(client, "control", "auth")
        payload = auth_event.message.get("payload", {})
        assert payload.get("ok") is False
        assert payload.get("code") == "version_negotiation_required"
        assert "version_negotiation_required" in payload.get("errors", [])

        await client.close()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task
        await server.stop()

    asyncio.run(run_flow())


def test_network_rejects_game_command_before_successful_hello_tls():
    async def run_flow():
        server = NetworkServer(
            host="127.0.0.1",
            port=0,
            cert_path=str(CERT_PATH),
            key_path=str(KEY_PATH),
        )
        await server.start()
        server_task = asyncio.create_task(server.run())

        uri = f"wss://localhost:{server.transport.port}"
        client = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        await client.connect()

        command = GameCommand.create(CMD_NEXT_PHASE, player_id="p1")
        await client.transport.send(CommandMessage(command=command, client_last_event_id=0))
        error_event = await _wait_for(client, "game", "error")
        errors = error_event.message.get("payload", {}).get("errors", [])
        assert "version_negotiation_required" in errors

        await client.close()
        server_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await server_task
        await server.stop()

    asyncio.run(run_flow())
