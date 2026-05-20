#!/usr/bin/env python3

from __future__ import annotations

import argparse
import asyncio
import contextlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from warhammer40k_ai.engine.command_kinds import CMD_EXECUTE_SETUP_PHASE, CMD_REQUEST_DECISION, CMD_RESOLVE_DECISION
from warhammer40k_ai.engine.commands import GameCommand
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_CHOOSE_PLAGUE,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
    DECISION_SHADOW_ASSIGNMENT,
)
from warhammer40k_ai.network.client import NetworkClient
from warhammer40k_ai.network.game_session import NetworkGameSession
from warhammer40k_ai.network.server import NetworkServer
from warhammer40k_ai.version import get_app_version

FORMATION_DECISION_TYPES = {
    DECISION_ATTACH_LEADER,
    DECISION_ATTACH_SUPPORT_ARTILLERY,
    DECISION_ASSIGN_TRANSPORT,
    DECISION_CHOOSE_PLAGUE,
    DECISION_CHOOSE_PLAYER_COLOR,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_RESERVES,
    DECISION_SHADOW_ASSIGNMENT,
}

DEPLOYMENT_DECISION_TYPES = {
    DECISION_CHOOSE_DEPLOYMENT_ZONE,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_NEXT_DEPLOY_UNIT,
}


@dataclass
class SmokeStats:
    errors: list[str]
    resync_reasons: list[str]
    resolved_command_ids: list[str]
    flushed_commands: list[str]
    decision_requests: int = 0
    formation_resolutions: int = 0
    deployment_resolutions: int = 0
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


async def _drain_available(
    sessions: list[NetworkGameSession],
    stats: SmokeStats,
) -> None:
    for session in sessions:
        while True:
            try:
                event = await session.client.next_message(timeout=0.0)
            except asyncio.TimeoutError:
                break
            await _handle_session_event(session, event, stats)


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


def _server_pending_decisions(server: NetworkServer, decision_types: set[str]) -> list[object]:
    server_game = server.game
    server_queue = getattr(server_game, "decision_queue", None) if server_game is not None else None
    if server_queue is None or not hasattr(server_queue, "list"):
        return []
    return [
        request
        for request in list(server_queue.list() or [])
        if str(getattr(request, "decision_type", "") or "") in decision_types
    ]


def _server_pending_formation_decisions(server: NetworkServer) -> list[object]:
    pending_fn = getattr(server, "_pending_formation_decisions", None)
    if callable(pending_fn):
        return list(pending_fn() or [])
    return _server_pending_decisions(server, FORMATION_DECISION_TYPES)


def _server_pending_harmless_decisions(server: NetworkServer) -> list[object]:
    return _server_pending_decisions(server, {DECISION_CHOOSE_PLAYER_COLOR})


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


def _select_first_legal_option(request: object):
    for option in list(getattr(request, "options", []) or []):
        option_id = str(getattr(option, "option_id", "") or "")
        if not option_id:
            continue
        action_id_for_option = getattr(request, "action_id_for_option_id", None)
        candidate_mask_for_action = getattr(request, "candidate_mask_for_action_id", None)
        action_id = action_id_for_option(option_id) if callable(action_id_for_option) else ""
        if action_id and callable(candidate_mask_for_action) and candidate_mask_for_action(action_id) is False:
            continue
        return option
    return None


def _select_matching_request(
    sessions: list[NetworkGameSession],
    server_requests: list[object],
) -> tuple[NetworkGameSession, object] | None:
    for request in sorted(
        list(server_requests or []),
        key=lambda req: (
            str(getattr(req, "player_id", "") or ""),
            str(getattr(req, "decision_type", "") or ""),
            str(getattr(req, "decision_id", "") or ""),
        ),
    ):
        request_player = str(getattr(request, "player_id", "") or "")
        decision_id = str(getattr(request, "decision_id", "") or "")
        if not request_player or not decision_id:
            continue
        for session in sessions:
            if str(session.client.player_id or "") == request_player and _local_has_decision(session, decision_id):
                return session, request
    return None


async def _resolve_request(
    session: NetworkGameSession,
    request: object,
    stats: SmokeStats,
) -> None:
    option = _select_first_legal_option(request)
    if option is None:
        raise RuntimeError(
            f"No legal option found for {getattr(request, 'decision_type', '')} "
            f"{getattr(request, 'decision_id', '')}."
        )
    result_payload = dict(getattr(option, "payload", {}) or {})
    command = GameCommand.create(
        CMD_RESOLVE_DECISION,
        player_id=getattr(request, "player_id", None),
        payload={
            "decision_id": getattr(request, "decision_id", ""),
            "option_id": getattr(option, "option_id", ""),
            "result_payload": result_payload,
        },
    )
    result = session.game_proxy.apply_command(command)
    if not bool(getattr(result, "ok", False)):
        errors = list(getattr(result, "errors", ()) or ())
        raise RuntimeError(
            f"Local decision resolution rejected for {getattr(request, 'decision_type', '')}: {errors}"
        )
    for queued in list(getattr(session, "_outgoing", []) or []):
        payload = dict(getattr(queued, "payload", {}) or {})
        decision_id = str(payload.get("decision_id", "") or "")
        queued_request = None
        game = session.game
        queue = getattr(game, "decision_queue", None) if game is not None else None
        if decision_id and queue is not None and hasattr(queue, "get"):
            queued_request = queue.get(decision_id)
        stats.flushed_commands.append(
            ":".join(
                [
                    str(getattr(queued, "command_id", "") or ""),
                    str(getattr(queued, "kind", "") or ""),
                    str(getattr(queued_request, "decision_type", "") or ""),
                    decision_id,
                ]
            )
        )
    await session.flush_outgoing()
    stats.resolved_command_ids.append(str(command.command_id))


async def _resolve_one_decision_if_available(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
    stats: SmokeStats,
) -> bool:
    selected = _select_harmless_decision(sessions, server)
    if selected is None:
        return False
    session, request = selected
    await _resolve_request(session, request, stats)
    return True


async def _resolve_all_formation_decisions(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
    *,
    timeout: float,
    stats: SmokeStats,
) -> int:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    resolved = 0
    while loop.time() < deadline:
        await _drain_available(sessions, stats)
        pending = _server_pending_formation_decisions(server)
        server_phase = _server_setup_phase_name(server)
        if not pending and server_phase == "DEPLOY_ARMIES":
            return resolved
        if not pending:
            await asyncio.sleep(0.05)
            continue
        selected = _select_matching_request(sessions, pending)
        if selected is None:
            await asyncio.sleep(0.05)
            continue
        session, request = selected
        await _resolve_request(session, request, stats)
        resolved += 1
        stats.formation_resolutions += 1
        await asyncio.sleep(0.05)
    pending_types = [str(getattr(req, "decision_type", "") or "") for req in _server_pending_formation_decisions(server)]
    raise TimeoutError(
        f"Timed out resolving formation decisions: "
        f"server_phase={_server_setup_phase_name(server)} pending={pending_types}"
    )


def _server_setup_phase_name(server: NetworkServer) -> str:
    game = server.game
    if game is None:
        return ""
    phase = game.get_current_setup_phase() if hasattr(game, "get_current_setup_phase") else getattr(game, "setup_phase", None)
    return str(getattr(phase, "name", "") or phase or "")


async def _wait_for_setup_phase(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
    phase_name: str,
    *,
    timeout: float,
    stats: SmokeStats,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    expected = str(phase_name or "")
    server_phase = ""
    local_phases: list[str] = []
    while loop.time() < deadline:
        await _drain_available(sessions, stats)
        server_phase = _server_setup_phase_name(server)
        if _server_setup_phase_name(server) == expected:
            local_phases = []
            for session in sessions:
                game = session.game
                phase = game.get_current_setup_phase() if game is not None and hasattr(game, "get_current_setup_phase") else None
                local_phases.append(str(getattr(phase, "name", "") or phase or ""))
            if all(phase == expected for phase in local_phases):
                return
        else:
            local_phases = []
            for session in sessions:
                game = session.game
                phase = game.get_current_setup_phase() if game is not None and hasattr(game, "get_current_setup_phase") else None
                local_phases.append(str(getattr(phase, "name", "") or phase or ""))
        await asyncio.sleep(0.05)
    pending_types = [str(getattr(req, "decision_type", "") or "") for req in _server_pending_formation_decisions(server)]
    pending_types.extend(
        str(getattr(req, "decision_type", "") or "")
        for req in _server_pending_decisions(server, DEPLOYMENT_DECISION_TYPES)
    )
    setup_task = getattr(server, "_setup_task", None)
    setup_task_error = ""
    if setup_task is not None and setup_task.done() and not setup_task.cancelled():
        exc = setup_task.exception()
        if exc is not None:
            setup_task_error = f"; setup_task_error={type(exc).__name__}: {exc}"
    raise TimeoutError(
        f"Timed out waiting for setup phase {expected}; "
        f"server_phase={server_phase}; local_phases={local_phases}; pending={pending_types}{setup_task_error}."
    )


async def _initialize_network_deployment(
    session: NetworkGameSession,
) -> None:
    command = GameCommand.create(
        CMD_EXECUTE_SETUP_PHASE,
        player_id=session.client.player_id,
        payload={"manual_phases": True},
    )
    result = session.game_proxy.apply_command(command)
    if not bool(getattr(result, "ok", False)):
        errors = list(getattr(result, "errors", ()) or ())
        raise RuntimeError(f"Local deployment initialization rejected: {errors}")
    await session.flush_outgoing()


async def _resolve_one_deployment_decision(
    sessions: list[NetworkGameSession],
    server: NetworkServer,
    *,
    timeout: float,
    stats: SmokeStats,
) -> bool:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await _drain_available(sessions, stats)
        pending = _server_pending_decisions(server, DEPLOYMENT_DECISION_TYPES)
        selected = _select_matching_request(sessions, pending)
        if selected is not None:
            session, request = selected
            await _resolve_request(session, request, stats)
            stats.deployment_resolutions += 1
            return True
        await asyncio.sleep(0.05)
    pending_types = [str(getattr(req, "decision_type", "") or "") for req in _server_pending_decisions(server, DEPLOYMENT_DECISION_TYPES)]
    raise TimeoutError(f"Timed out waiting for deployment decision request: {pending_types}")


async def _drain_for(
    sessions: list[NetworkGameSession],
    *,
    seconds: float,
    stats: SmokeStats,
) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, float(seconds))
    while loop.time() < deadline:
        await _drain_available(sessions, stats)
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


def _assert_no_errors_or_resync_storm(stats: SmokeStats, *, expected_clients: int) -> None:
    if stats.errors:
        raise RuntimeError(
            "Network smoke observed ErrorMessage payloads: "
            f"{stats.errors}; resolved_command_ids={list(stats.resolved_command_ids)}; "
            f"flushed_commands={list(stats.flushed_commands)}"
        )
    allowed_reasons = {"", "formation_reveal"}
    unexpected = [reason for reason in stats.resync_reasons if reason not in allowed_reasons]
    if unexpected:
        raise RuntimeError(f"Unexpected resync reason(s): {unexpected}")
    reason_counts = Counter(str(reason or "") for reason in stats.resync_reasons)
    if any(count > max(1, int(expected_clients)) for count in reason_counts.values()):
        raise RuntimeError(f"Unexpected resync storm: {stats.resync_reasons}")


async def _run_smoke(args: argparse.Namespace) -> str:
    army1_name, army1_text = _army_text(str(args.player1_army))
    army2_name, army2_text = _army_text(str(args.player2_army))
    timeout = float(args.timeout)
    stats = SmokeStats(errors=[], resync_reasons=[], resolved_command_ids=[], flushed_commands=[])

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
        formation_resolved = await _resolve_all_formation_decisions(
            sessions,
            server,
            timeout=timeout,
            stats=stats,
        )
        await _wait_for_setup_phase(sessions, server, "DEPLOY_ARMIES", timeout=timeout, stats=stats)
        await _initialize_network_deployment(session1)
        deployment_resolved = await _resolve_one_deployment_decision(
            sessions,
            server,
            timeout=timeout,
            stats=stats,
        )
        await _drain_for(
            sessions,
            seconds=float(args.post_decision_drain_seconds),
            stats=stats,
        )
        _assert_no_errors_or_resync_storm(stats, expected_clients=len(sessions))

        summary = (
            "network_loopback_smoke=ok "
            f"port={server.transport.port} "
            f"snapshots={stats.snapshots} "
            f"decision_requests={stats.decision_requests} "
            f"resolved_decision={str(resolved).lower()} "
            f"formation_resolved={formation_resolved} "
            f"deployment_resolved={str(deployment_resolved).lower()} "
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
