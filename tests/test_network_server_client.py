import asyncio
import contextlib
from pathlib import Path

from warhammer40k_ai.engine.command_kinds import CMD_NEXT_PHASE
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.network.client import NetworkClient
from warhammer40k_ai.network.messages import CommandMessage
from warhammer40k_ai.network.server import NetworkServer

CERT_PATH = Path("tests/fixtures/tls/server.crt")
KEY_PATH = Path("tests/fixtures/tls/server.key")


async def _wait_for(client: NetworkClient, category: str, message_type: str, timeout: float = 10.0):
    while True:
        event = await client.next_message(timeout=timeout)
        client.handle_message(event)
        if event.category == category and event.message_type == message_type:
            return event


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
        await _wait_for(client1, "game", "snapshot")
        await _wait_for(client2, "game", "snapshot")

        command = GameCommand.create(CMD_NEXT_PHASE, player_id=client1.player_id)
        await client1.send_command(command)
        await _wait_for(client1, "game", "event")

        spectator = NetworkClient(uri=uri, ca_cert=str(CERT_PATH))
        await spectator.connect()
        await spectator.send_hello("Spec")
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
