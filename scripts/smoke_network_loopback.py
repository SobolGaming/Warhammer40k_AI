#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import contextlib
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from warhammer40k_ai.engine.command_kinds import CMD_REQUEST_DECISION, CMD_RESOLVE_DECISION
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PLAYER_COLOR
from warhammer40k_ai.network.client import NetworkClient
from warhammer40k_ai.network.game_session import NetworkGameSession
from warhammer40k_ai.network.server import NetworkServer
from warhammer40k_ai.version import get_app_version


@dataclass
class SmokeStats:
    errors: list[str]
    resync_reasons: list[str]
    resolved_command_ids: list[str]
    decision_requests: int = 0
    snapshots: int = 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a localhost two-client network loopback smoke and fail on protocol/session crashes.",
    )
    parser.add_argument("--player1-army", default="army_lists/chaos_test.txt")
    parser.add_argument("--player2-army", default="army_lists/aeldari_test.txt")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--post-decision-drain-seconds", type=float, default=1.0)
    return parser


def _army_text(path_value: str) -> tuple[str, str]:
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.name, path.read_text(encoding="utf-8")


async def _server_runner(server: NetworkServer) -> None:
    await server.run()


async def _wait_for_event(
    session: NetworkGameSession,
    *,
    category: str,
    message_type: str,
    timeout: float,
    stats: SmokeStats,
):
    while True:
        event = await session.client.next_message(timeout=timeout)
        await _handle_session_event(session, event, stats)
        if event.category == category and event.message_type == message_type:
            return event


async def _wait_for_control_ok(
    session: NetworkGameSession,
    message_type: str,
    *,
    timeout: float,
    stats: SmokeStats,
) -> dict:
    event = await _wait_for_event(
        session,
        category="control",
        message_type=message_type,
        timeout=timeout,
        stats=stats,
    )
    payload = dict(event.message.get("payload", {}) or {})
    if payload.get("ok") is False:
        errors = list(payload.get("errors", []) or [])
        raise RuntimeError(f"{message_type} failed: {errors}")
    return payload


async def _handle_session_event(session: NetworkGameSession, event, stats: SmokeStats) -> None:
    if event.category == "game" and event.message_type == "error":
        payload = dict(event.message.get("payload", {}) or {})
        errors = list(payload.get("errors", []) or [])
        context = dict(payload.get("context", {}) or {})
        stats.errors.extend(f"{error} context={context}" for error in errors)
    elif event.category == "game" and event.message_type == "resync":
        payload = dict(event.message.get("payload", {}) or {})
        stats.resync_reasons.append(str(payload.get("reason", "") or ""))
    elif event.category == "game" and event.message_type == "snapshot":
        stats.snapshots += 1
    elif event.category == "game" and event.message_type == "command":
        command = dict((event.message.get("payload", {}) or {}).get("command", {}) or {})
        if str(command.get("kind", "") or "") == CMD_REQUEST_DECISION:
            stats.decision_requests += 1
    await session.handle_message(event)


async def _connect_player(
    uri: str,
    *,
    display_name: str,
    role: str,
    army_name: str,
    army_text: str,
    timeout: float,
    stats: SmokeStats,
) -> tuple[NetworkClient, NetworkGameSession]:
    client = NetworkClient(uri=uri, response_timeout=timeout)
    session = NetworkGameSession(client, allow_commands=True)
    await client.connect()

    await client.send_hello(display_name, app_version=get_app_version())
    hello = await _wait_for_control_ok(session, "hello", timeout=timeout, stats=stats)
    if hello.get("server_version") != get_app_version():
        raise RuntimeError(
            f"Server version mismatch in smoke: server={hello.get('server_version')} client={get_app_version()}."
        )

    await client.send_auth()
    await _wait_for_control_ok(session, "auth", timeout=timeout, stats=stats)

    await client.send_role_select(role)
    role_payload = await _wait_for_control_ok(session, "role_select", timeout=timeout, stats=stats)
    if role_payload.get("role") != role:
        raise RuntimeError(f"Expected role {role}, got {role_payload.get('role')}.")

    await client.send_army_submit(army_text, list_name=army_name)
    army_payload = await _wait_for_control_ok(session, "army_submit", timeout=timeout, stats=stats)
    if army_payload.get("status") != "validated":
        raise RuntimeError(f"Army submit did not validate for {role}: {army_payload}.")

    return client, session


async def _ready_and_wait_for_start(
    sessions: Iterable[NetworkGameSession],
    *,
    timeout: float,
    stats: SmokeStats,
) -> None:
    session_list = list(sessions)
    for session in session_list:
        await session.client.send_ready(True)
    for session in session_list:
        ready = await _wait_for_control_ok(session, "ready", timeout=timeout, stats=stats)
        if ready.get("ready") is not True:
            raise RuntimeError(f"Ready response did not confirm ready=true: {ready}.")
    for session in session_list:
        await _wait_for_event(
            session,
            category="control",
            message_type="start_game",
            timeout=timeout,
            stats=stats,
        )
    for session in session_list:
        await _wait_for_event(
            session,
            category="game",
            message_type="snapshot",
            timeout=timeout,
            stats=stats,
        )


async def _wait_for_setup_or_decision(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
    *,
    timeout: float,
    stats: SmokeStats,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    initial_phases = [str(getattr(session.game, "setup_phase", "") or "") for session in sessions]
    initial_snapshots = int(stats.snapshots)
    while loop.time() < deadline:
        for session in sessions:
            while True:
                try:
                    event = await session.client.next_message(timeout=0.0)
                except asyncio.TimeoutError:
                    break
                await _handle_session_event(session, event, stats)
        if _select_harmless_decision(sessions, server) is not None:
            return
        current_phases = [str(getattr(session.game, "setup_phase", "") or "") for session in sessions]
        if (
            current_phases != initial_phases
            and stats.snapshots > initial_snapshots
            and not _server_pending_harmless_decisions(server)
        ):
            return
        await asyncio.sleep(0.05)
    raise TimeoutError("Timed out waiting for setup broadcasts or a decision request.")


def _pending_decisions(session: NetworkGameSession) -> list[object]:
    game = session.game
    queue = getattr(game, "decision_queue", None) if game is not None else None
    if queue is None or not hasattr(queue, "list"):
        return []
    return list(queue.list() or [])


def _pending_harmless_decisions(session: NetworkGameSession) -> list[object]:
    return [
        request
        for request in _pending_decisions(session)
        if str(getattr(request, "decision_type", "") or "") == DECISION_CHOOSE_PLAYER_COLOR
    ]


def _local_has_decision(session: NetworkGameSession, decision_id: str) -> bool:
    return any(str(getattr(request, "decision_id", "") or "") == decision_id for request in _pending_decisions(session))


def _server_pending_harmless_decisions(server: NetworkServer) -> list[object]:
    server_game = server.game
    server_queue = getattr(server_game, "decision_queue", None) if server_game is not None else None
    if server_queue is None or not hasattr(server_queue, "list"):
        return []
    return [
        request
        for request in list(server_queue.list() or [])
        if str(getattr(request, "decision_type", "") or "") == DECISION_CHOOSE_PLAYER_COLOR
    ]


def _select_harmless_decision(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
) -> tuple[NetworkGameSession, object] | None:
    server_requests = _server_pending_harmless_decisions(server)
    for session in sessions:
        player_id = str(session.client.player_id or "")
        for request in server_requests:
            request_player = str(getattr(request, "player_id", "") or "")
            decision_id = str(getattr(request, "decision_id", "") or "")
            options = list(getattr(request, "options", []) or [])
            if request_player == player_id and decision_id and options and _local_has_decision(session, decision_id):
                return session, request
    return None


async def _resolve_one_decision_if_available(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
    stats: SmokeStats,
) -> bool:
    selected = _select_harmless_decision(sessions, server)
    if selected is None:
        return False
    session, request = selected
    option = list(getattr(request, "options", []) or [])[0]
    command = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=getattr(request, "player_id", None),
        payload={
            "decision_id": getattr(request, "decision_id", ""),
            "option_id": getattr(option, "option_id", ""),
            "result_payload": {},
        },
    )
    result = session.game_proxy.apply_command(command)
    if not bool(getattr(result, "ok", False)):
        errors = list(getattr(result, "errors", ()) or ())
        raise RuntimeError(f"Local decision resolution rejected: {errors}")
    await session.flush_outgoing()
    stats.resolved_command_ids.append(str(command.command_id))
    return True


async def _drain_for(
    sessions: list[NetworkGameSession],
    *,
    seconds: float,
    stats: SmokeStats,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, float(seconds))
    while loop.time() < deadline:
        for session in sessions:
            while True:
                try:
                    event = await session.client.next_message(timeout=0.0)
                except asyncio.TimeoutError:
                    break
                await _handle_session_event(session, event, stats)
        await asyncio.sleep(0.05)


def _assert_sessions_loaded(sessions: list[NetworkGameSession]) -> None:
    for session in sessions:
        if session.game is None:
            raise RuntimeError(f"{session.client.role} did not load a game snapshot.")
        if session.game_proxy is None:
            raise RuntimeError(f"{session.client.role} did not create a NetworkGameProxy.")
        if not session.client.player_id:
            raise RuntimeError(f"{session.client.role} did not receive a player_id from snapshot load.")
        local_players = [
            player
            for player in list(getattr(session.game, "players", []) or [])
            if bool(getattr(player, "has_control", lambda: False)())
        ]
        if len(local_players) != 1:
            raise RuntimeError(f"{session.client.role} expected exactly one locally controlled player.")
        if str(getattr(local_players[0], "id", "") or "") != str(session.client.player_id):
            raise RuntimeError(f"{session.client.role} local control does not match client.player_id.")


def _assert_no_errors_or_resync_storm(stats: SmokeStats) -> None:
    if stats.errors:
        raise RuntimeError(
            "Network smoke observed ErrorMessage payloads: "
            f"{stats.errors}; resolved_command_ids={list(stats.resolved_command_ids)}"
        )
    allowed_reasons = {"", "formation_reveal"}
    unexpected = [reason for reason in stats.resync_reasons if reason not in allowed_reasons]
    if unexpected:
        raise RuntimeError(f"Unexpected resync reason(s): {unexpected}")
    if len(stats.resync_reasons) > 1:
        raise RuntimeError(f"Unexpected resync storm: {stats.resync_reasons}")


async def _run_smoke(args: argparse.Namespace) -> str:
    army1_name, army1_text = _army_text(str(args.player1_army))
    army2_name, army2_text = _army_text(str(args.player2_army))
    timeout = float(args.timeout)
    stats = SmokeStats(errors=[], resync_reasons=[], resolved_command_ids=[])

    server = NetworkServer(host=str(args.host), port=0, cert_path=None, key_path=None)
    clients: list[NetworkClient] = []
    server_task: asyncio.Task | None = None
    summary = ""
    try:
        await server.start()
        server_task = asyncio.create_task(_server_runner(server))
        uri = f"ws://{args.host}:{server.transport.port}"

        client1, session1 = await _connect_player(
            uri,
            display_name="Loopback Player 1",
            role="player1",
            army_name=army1_name,
            army_text=army1_text,
            timeout=timeout,
            stats=stats,
        )
        clients.append(client1)
        client2, session2 = await _connect_player(
            uri,
            display_name="Loopback Player 2",
            role="player2",
            army_name=army2_name,
            army_text=army2_text,
            timeout=timeout,
            stats=stats,
        )
        clients.append(client2)
        sessions = [session1, session2]

        await _ready_and_wait_for_start(sessions, timeout=timeout, stats=stats)
        _assert_sessions_loaded(sessions)
        await _wait_for_setup_or_decision(sessions, server, timeout=timeout, stats=stats)
        resolved = await _resolve_one_decision_if_available(sessions, server, stats)
        await _drain_for(
            sessions,
            seconds=float(args.post_decision_drain_seconds),
            stats=stats,
        )
        _assert_no_errors_or_resync_storm(stats)

        summary = (
            "network_loopback_smoke=ok "
            f"port={server.transport.port} "
            f"snapshots={stats.snapshots} "
            f"decision_requests={stats.decision_requests} "
            f"resolved_decision={str(resolved).lower()} "
            f"resyncs={len(stats.resync_reasons)}"
        )
    finally:
        for client in clients:
            await client.close()
        if server_task is not None:
            server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await server_task
        await server.stop()
    return summary


def main() -> int:
    args = _build_parser().parse_args()
    summary = asyncio.run(_run_smoke(args))
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
