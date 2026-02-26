from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional

from .command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_SELECT_MISSION,
)
from .commands import GameCommand
from .decisions import DecisionRequest
from .game import Game
from .phase import SetupPhase


class AuthoritativeSessionDriver:
    """Shared setup orchestration used by authoritative runtimes."""

    def __init__(
        self,
        *,
        get_game: Callable[[], Optional[Game]],
        is_running: Callable[[], bool],
        apply_command: Callable[[GameCommand], Awaitable[object]],
        apply_command_with_broadcast: Callable[[GameCommand, bool], Awaitable[object]],
        choose_random_mission: Callable[[Game], tuple[dict, int]],
        queue_formation_decisions: Callable[[], Awaitable[list[DecisionRequest]]],
        pending_formation_decisions: Callable[[], list[DecisionRequest]],
        wait_for_formation_decisions: Callable[[], Awaitable[None]],
        broadcast_resync_all: Callable[[str], Awaitable[None]],
        set_formation_buffering: Callable[[bool], None],
        should_wait_for_formation_decisions: Callable[[], bool] | None = None,
        should_handle_phase: Callable[[SetupPhase], bool] | None = None,
        skip_muster_phase: bool = True,
        build_execute_setup_payload: Callable[[SetupPhase], dict] | None = None,
    ) -> None:
        self._get_game = get_game
        self._is_running = is_running
        self._apply_command = apply_command
        self._apply_command_with_broadcast = apply_command_with_broadcast
        self._choose_random_mission = choose_random_mission
        self._queue_formation_decisions = queue_formation_decisions
        self._pending_formation_decisions = pending_formation_decisions
        self._wait_for_formation_decisions = wait_for_formation_decisions
        self._broadcast_resync_all = broadcast_resync_all
        self._set_formation_buffering = set_formation_buffering
        self._should_wait_for_formation_decisions = should_wait_for_formation_decisions or (lambda: True)
        self._should_handle_phase = should_handle_phase or (lambda _phase: True)
        self._skip_muster_phase = bool(skip_muster_phase)
        self._build_execute_setup_payload = build_execute_setup_payload or (lambda _phase: {})
        self._setup_lock = asyncio.Lock()

    async def run_setup_sequence(self) -> None:
        async with self._setup_lock:
            game = self._get_game()
            if game is None:
                return
            if bool(getattr(game, "setup_complete", False)):
                return

            if game.get_current_setup_phase() == SetupPhase.MUSTER_ARMIES:
                if not self._skip_muster_phase:
                    await self._apply_command(self._create_execute_setup_command(SetupPhase.MUSTER_ARMIES))
                await self._apply_command(GameCommand.create(CMD_ADVANCE_SETUP_PHASE))

            while self._is_running() and self._get_game() is game and game.is_in_setup_phase():
                phase = game.get_current_setup_phase()
                if not self._should_handle_phase(phase):
                    return
                if phase == SetupPhase.SELECT_MISSION_OBJECTIVES:
                    combo, layout = self._choose_random_mission(game)
                    await self._apply_command(
                        GameCommand.create(
                            CMD_SELECT_MISSION,
                            payload={"combination": dict(combo or {}), "layout": layout},
                        )
                    )
                    await self._apply_command(self._create_execute_setup_command(phase))
                    await self._apply_command(GameCommand.create(CMD_ADVANCE_SETUP_PHASE))
                    continue
                if phase == SetupPhase.CREATE_BATTLEFIELD:
                    await self._apply_command(self._create_execute_setup_command(phase))
                    await self._apply_command(GameCommand.create(CMD_ADVANCE_SETUP_PHASE))
                    continue
                if phase == SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER:
                    await self._apply_command(self._create_execute_setup_command(phase))
                    await self._apply_command(GameCommand.create(CMD_ADVANCE_SETUP_PHASE))
                    continue
                if phase == SetupPhase.DECLARE_BATTLE_FORMATIONS:
                    await self._queue_formation_decisions()
                    pending = self._pending_formation_decisions()
                    if pending:
                        if not self._should_wait_for_formation_decisions():
                            return
                        self._set_formation_buffering(True)
                        try:
                            await self._wait_for_formation_decisions()
                            if not self._is_running() or self._get_game() is None:
                                return
                            await self._apply_command_with_broadcast(
                                self._create_execute_setup_command(phase),
                                False,
                            )
                            await self._apply_command_with_broadcast(
                                GameCommand.create(CMD_ADVANCE_SETUP_PHASE),
                                False,
                            )
                        finally:
                            self._set_formation_buffering(False)
                        await self._broadcast_resync_all("formation_reveal")
                    else:
                        await self._apply_command(self._create_execute_setup_command(phase))
                        await self._apply_command(GameCommand.create(CMD_ADVANCE_SETUP_PHASE))
                    break
                break

    def _create_execute_setup_command(self, phase: SetupPhase) -> GameCommand:
        payload = dict(self._build_execute_setup_payload(phase) or {})
        return GameCommand.create(CMD_EXECUTE_SETUP_PHASE, payload=payload)
