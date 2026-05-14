from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from ..engine.headless_policy_controller import HeadlessPolicyDecisionController
from ..ml.llm_policy_adapters import build_llm_policy_orchestrator_from_config_file
from .client import NetworkClient
from .game_session import GameUpdate, NetworkGameSession
from .server import NetworkServer
import logging

from ..console import configure_console_encoding

logger = logging.getLogger(__name__)

def setup_logging(log_level) -> logging.Logger:
    """Configure logging."""
    print(f"Setting up logging at level {log_level}")
    root_logger = logging.getLogger()
    root_logger.setLevel(logging._nameToLevel[log_level])

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(message)s")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging._nameToLevel[log_level])
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Suppress noisy modules
    for module in [
        "pygame",
        "warhammer40k_ai.roster.army",
        "warhammer40k_ai.units.unit",
        "warhammer40k_ai.units.model",
        "warhammer40k_ai.engine.game",
        "warhammer40k_ai.battlefield.map",
    ]:
        logging.getLogger(module).setLevel(logging.ERROR)

    return logging.getLogger(__name__)

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warhammer40k AI network server/client")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    server = subparsers.add_parser("server", help="Run the network server")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--cert", required=True, help="TLS certificate path")
    server.add_argument("--key", required=True, help="TLS private key path")
    server.add_argument("--join-code", help="Optional join code")
    server.add_argument("--ping-interval", type=float, default=20.0)
    server.add_argument("--ping-timeout", type=float, default=20.0)
    server.add_argument(
        "-l",
        "--log",
        dest="log_level",
        help="Set the logging level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )

    client = subparsers.add_parser("client", help="Run the network client")
    client.add_argument("--server", required=True, help="Server URI (wss://host:port)")
    client.add_argument("--ca-cert", help="CA certificate path")
    client.add_argument("--insecure", action="store_true", help="Disable TLS verification (dev only)")
    client.add_argument("--display-name", default="Client")
    client.add_argument("--join-code", help="Join code")
    client.add_argument("--reconnect-token", help="Reconnect token")
    client.add_argument("--role", choices=["player1", "player2", "spectator"], help="Role selection")
    client.add_argument("--army-file", help="Army list file to submit")
    client.add_argument("--ready", action="store_true", help="Mark ready after submit")
    client.add_argument("--response-timeout", type=float, default=NetworkClient.DEFAULT_RESPONSE_TIMEOUT)
    client.add_argument(
        "-l",
        "--log",
        dest="log_level",
        help="Set the logging level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )
    

    ui_client = subparsers.add_parser("client-ui", help="Run the network client with pygame UI")
    ui_client.add_argument("--server", required=True, help="Server URI (wss://host:port)")
    ui_client.add_argument("--ca-cert", help="CA certificate path")
    ui_client.add_argument("--insecure", action="store_true", help="Disable TLS verification (dev only)")
    ui_client.add_argument("--display-name", default="Client")
    ui_client.add_argument("--join-code", help="Join code")
    ui_client.add_argument("--reconnect-token", help="Reconnect token")
    ui_client.add_argument("--role", choices=["player1", "player2", "spectator"], help="Role selection")
    ui_client.add_argument("--army-file", help="Army list file to submit")
    ui_client.add_argument("--ready", action="store_true", help="Mark ready after submit")
    ui_client.add_argument("--response-timeout", type=float, default=NetworkClient.DEFAULT_RESPONSE_TIMEOUT)
    ui_client.add_argument(
        "-l",
        "--log",
        dest="log_level",
        help="Set the logging level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )

    headless_client = subparsers.add_parser("client-headless", help="Run a headless policy network client")
    headless_client.add_argument("--server", required=True, help="Server URI (wss://host:port)")
    headless_client.add_argument("--ca-cert", help="CA certificate path")
    headless_client.add_argument("--insecure", action="store_true", help="Disable TLS verification (dev only)")
    headless_client.add_argument("--display-name", default="HeadlessClient")
    headless_client.add_argument("--join-code", help="Join code")
    headless_client.add_argument("--reconnect-token", help="Reconnect token")
    headless_client.add_argument("--role", choices=["player1", "player2"], required=True, help="Controlled role")
    headless_client.add_argument("--army-file", help="Army list file to submit")
    headless_client.add_argument("--ready", action="store_true", help="Mark ready after submit")
    headless_client.add_argument("--response-timeout", type=float, default=NetworkClient.DEFAULT_RESPONSE_TIMEOUT)
    headless_client.add_argument(
        "--max-reserves-arrival-seconds",
        type=float,
        default=10.0,
        help="Hard wall-clock cap per reserves-arrival placement decision (default: 10.0).",
    )
    headless_client.add_argument(
        "--llm-policy-adapter-config",
        dest="llm_adapter_config",
        default="",
        help=(
            "Optional JSON config for LLM-backed policy adapters. "
            "Returned action ids are validated and fall back to deterministic rankers."
        ),
    )
    headless_client.add_argument(
        "-l",
        "--log",
        dest="log_level",
        help="Set the logging level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
    )

    return parser


async def _run_server(args: argparse.Namespace) -> None:
    server = NetworkServer(
        host=args.host,
        port=args.port,
        cert_path=args.cert,
        key_path=args.key,
        join_code=args.join_code,
        ping_interval=args.ping_interval,
        ping_timeout=args.ping_timeout,
    )
    await server.start()
    logger.info(f"Network server listening on {server.transport.host}:{server.transport.port}")
    try:
        await server.run()
    finally:
        await server.stop()


async def _wait_for_control(client: NetworkClient, expected_type: str, *, timeout: float | None = None):
    return await client.wait_for_control(expected_type, timeout=timeout)


async def _run_client(args: argparse.Namespace) -> None:
    client = NetworkClient(
        uri=args.server,
        ca_cert=args.ca_cert,
        insecure=args.insecure,
        response_timeout=args.response_timeout,
    )
    await client.connect()
    await client.send_hello(args.display_name)
    hello_msg = await _wait_for_control(client, "hello", timeout=args.response_timeout)
    hello_payload = hello_msg.get("payload", {})
    if not hello_payload.get("ok"):
        logger.info(f"Version mismatch: {hello_payload.get('errors', [])}")
        await client.close()
        return
    await client.send_auth(join_code=args.join_code, reconnect_token=args.reconnect_token)
    auth_msg = await _wait_for_control(client, "auth", timeout=args.response_timeout)
    payload = auth_msg.get("payload", {})
    if not payload.get("ok"):
        logger.error(f"Auth failed: {payload.get('errors', [])}")
        await client.close()
        return
    if args.role:
        await client.send_role_select(args.role)
        await _wait_for_control(client, "role_select", timeout=args.response_timeout)
    if args.army_file:
        text = Path(args.army_file).read_text(encoding="utf-8")
        await client.send_army_submit(text, list_name=Path(args.army_file).name)
        await _wait_for_control(client, "army_submit", timeout=args.response_timeout)
    if args.ready:
        await client.send_ready(True)
        await _wait_for_control(client, "ready", timeout=args.response_timeout)

    logger.info("Connected. Listening for updates...")
    try:
        while True:
            event = await client.next_message()
            client.handle_message(event)
            logger.info(f"[{event.category}] {event.message_type}")
    except asyncio.CancelledError:
        raise
    finally:
        await client.close()


async def _run_headless_client(args: argparse.Namespace) -> None:
    client = NetworkClient(
        uri=args.server,
        ca_cert=args.ca_cert,
        insecure=args.insecure,
        response_timeout=args.response_timeout,
    )
    session = NetworkGameSession(client, allow_commands=True)
    current_controller: HeadlessPolicyDecisionController | None = None

    def _bind_policy(update: GameUpdate) -> None:
        nonlocal current_controller
        player_id = client.player_id
        if not player_id:
            return
        ai_orchestrator = None
        if str(getattr(args, "llm_adapter_config", "") or "").strip():
            ai_orchestrator = build_llm_policy_orchestrator_from_config_file(str(args.llm_adapter_config))
        current_controller = HeadlessPolicyDecisionController(
            game=update.game_proxy,
            player_id=player_id,
            max_reserves_arrival_seconds=float(args.max_reserves_arrival_seconds),
            require_authoritative=False,
            ai_orchestrator=ai_orchestrator,
            auto_attach=True,
        )

    session.on_game_loaded = _bind_policy

    await client.connect()
    await client.send_hello(args.display_name)
    hello_msg = await _wait_for_control(client, "hello", timeout=args.response_timeout)
    hello_payload = hello_msg.get("payload", {})
    if not hello_payload.get("ok"):
        logger.info(f"Version mismatch: {hello_payload.get('errors', [])}")
        await client.close()
        return
    await client.send_auth(join_code=args.join_code, reconnect_token=args.reconnect_token)
    auth_msg = await _wait_for_control(client, "auth", timeout=args.response_timeout)
    payload = auth_msg.get("payload", {})
    if not payload.get("ok"):
        logger.error(f"Auth failed: {payload.get('errors', [])}")
        await client.close()
        return
    await client.send_role_select(str(args.role))
    role_msg = await _wait_for_control(client, "role_select", timeout=args.response_timeout)
    role_payload = role_msg.get("payload", {})
    if not role_payload.get("ok"):
        logger.error(f"Role selection failed: {role_payload.get('errors', [])}")
        await client.close()
        return
    if args.army_file:
        text = Path(args.army_file).read_text(encoding="utf-8")
        await client.send_army_submit(text, list_name=Path(args.army_file).name)
        army_msg = await _wait_for_control(client, "army_submit", timeout=args.response_timeout)
        army_payload = army_msg.get("payload", {})
        if not army_payload.get("ok"):
            logger.error(f"Army submission failed: {army_payload.get('errors', [])}")
            await client.close()
            return
    if args.ready:
        await client.send_ready(True)
        ready_msg = await _wait_for_control(client, "ready", timeout=args.response_timeout)
        ready_payload = ready_msg.get("payload", {})
        if not ready_payload.get("ok"):
            logger.error(f"Ready state update failed: {ready_payload.get('errors', [])}")
            await client.close()
            return

    logger.info("Connected. Waiting for game snapshot...")
    try:
        while session.game is None:
            event = await client.next_message(timeout=0.25)
            await session.handle_message(event)
        logger.info("Headless policy active. Listening for decisions...")
        while True:
            await session.poll_messages()
            await session.flush_outgoing()
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        raise
    finally:
        await client.close()


def main() -> None:
    configure_console_encoding()
    parser = _build_parser()
    args = parser.parse_args()
    setup_logging(args.log_level)
    if args.mode == "server":
        asyncio.run(_run_server(args))
        return
    if args.mode == "client":
        asyncio.run(_run_client(args))
        return
    if args.mode == "client-ui":
        from .pygame_client import run_pygame_network_client

        asyncio.run(
            run_pygame_network_client(
                uri=args.server,
                ca_cert=args.ca_cert,
                insecure=args.insecure,
                display_name=args.display_name,
                join_code=args.join_code,
                reconnect_token=args.reconnect_token,
                role=args.role,
                army_file=args.army_file,
                ready=args.ready,
                response_timeout=args.response_timeout,
            )
        )
        return
    if args.mode == "client-headless":
        asyncio.run(_run_headless_client(args))
        return
    raise ValueError(f"Unknown mode: {args.mode}")


if __name__ == "__main__":
    main()
