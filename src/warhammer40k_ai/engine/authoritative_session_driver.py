from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Optional

from .command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_RESOLVE_DECISION,
)
from .commands import GameCommand
from .decisions import DecisionOption, DecisionRequest
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
                    await self._resolve_mission_selection_request(game)
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

    async def _resolve_mission_selection_request(self, game: Game) -> None:
        request_fn = getattr(game, "request_mission_selection", None)
        if not callable(request_fn):
            raise RuntimeError("Game missing request_mission_selection for authoritative setup flow.")
        request = request_fn()
        pending = self._pending_request(game, request)
        if pending is None:
            return
        combo, layout = self._choose_random_mission(game)
        option = self._match_mission_option(request, combo)
        if option is None:
            raise RuntimeError("Chosen mission option did not match any emitted CHOOSE_MISSION option.")
        await self._apply_command(
            GameCommand.create(
                CMD_RESOLVE_DECISION,
                player_id=getattr(request, "player_id", None),
                payload={
                    "decision_id": request.decision_id,
                    "option_id": option.option_id,
                    "result_payload": {"layout": int(layout)},
                },
            )
        )

    @staticmethod
    def _pending_request(game: Game, request: DecisionRequest | None) -> DecisionRequest | None:
        if request is None:
            return None
        queue = getattr(game, "decision_queue", None)
        if queue is None or not hasattr(queue, "get"):
            return request
        return queue.get(str(getattr(request, "decision_id", "") or ""))

    @staticmethod
    def _match_mission_option(request: DecisionRequest, choice: dict | None) -> DecisionOption | None:
        selected = dict(choice or {})
        selected_pack_id = str(selected.get("pack_id", "") or "").strip()
        selected_combo_id = str(selected.get("combination_id", "") or selected.get("id", "") or "").strip()
        selected_primary = str(selected.get("primary", "") or "").strip()
        selected_deployment = str(selected.get("deployment", "") or "").strip()
        for option in list(getattr(request, "options", []) or []):
            payload = dict(getattr(option, "payload", {}) or {})
            combo = dict(payload.get("combination", {}) or {})
            combo_pack_id = str(combo.get("pack_id", "") or "").strip()
            combo_id = str(combo.get("combination_id", "") or combo.get("id", "") or "").strip()
            if selected_pack_id and combo_pack_id and combo_pack_id != selected_pack_id:
                continue
            if selected_combo_id and combo_id:
                if combo_id == selected_combo_id:
                    return option
                continue
            combo_primary = str(combo.get("primary", "") or "").strip()
            combo_deployment = str(combo.get("deployment", "") or "").strip()
            if selected_primary and combo_primary and combo_primary != selected_primary:
                continue
            if selected_deployment and combo_deployment and combo_deployment != selected_deployment:
                continue
            return option
        return None
