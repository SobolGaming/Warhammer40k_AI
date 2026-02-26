from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from .authoritative_session_driver import AuthoritativeSessionDriver
from .command_channel import InProcessCommandChannel
from .player_intent_gateway import IntentRoutedGameProxy, PlayerIntentGateway
from .command_dispatcher import CommandResult
from .commands import GameCommand
from .game import Game
from .mission_selection import iter_mission_combinations
from .phase import SetupPhase
from ..utility.dice import get_dice_roll
from ..utility.game_context import game_context, roll_context

_DRIVER_MANAGED_SETUP_PHASES = {
    SetupPhase.MUSTER_ARMIES,
    SetupPhase.SELECT_MISSION_OBJECTIVES,
    SetupPhase.CREATE_BATTLEFIELD,
    SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
}


@dataclass(frozen=True)
class LocalPlayerFacade:
    facade_id: str
    player_id: str


class LocalAuthoritativeRuntime:
    """Shared local authoritative composition (no network loopback)."""

    def __init__(
        self,
        game: Game,
        *,
        choose_random_mission=None,
    ) -> None:
        self.game = game
        self.command_channel = InProcessCommandChannel()
        self.local_facades: list[LocalPlayerFacade] = []
        self._running = True
        self._formation_buffering = False
        self._choose_random_mission = choose_random_mission or self._default_choose_random_mission
        self.intent_gateway = PlayerIntentGateway(
            apply_command=self._submit_local_command,
            request_decision=self._submit_local_decision_request,
        )
        self.game_proxy = IntentRoutedGameProxy(self.game, self.intent_gateway)
        self._session_driver = AuthoritativeSessionDriver(
            get_game=lambda: self.game,
            is_running=lambda: self._running,
            apply_command=self._apply_command_default,
            apply_command_with_broadcast=self._apply_command_with_broadcast,
            choose_random_mission=self._choose_random_mission,
            queue_formation_decisions=self._queue_formation_decisions,
            pending_formation_decisions=self._pending_formation_decisions,
            wait_for_formation_decisions=self._wait_for_formation_decisions,
            broadcast_resync_all=self._broadcast_resync_all,
            set_formation_buffering=self._set_formation_buffering,
            should_wait_for_formation_decisions=lambda: False,
            should_handle_phase=lambda phase: phase in _DRIVER_MANAGED_SETUP_PHASES,
        )

    def register_local_player_facade(self, facade_id: str, player_id: str) -> None:
        key = str(facade_id or "").strip()
        pid = str(player_id or "").strip()
        if not key:
            raise ValueError("facade_id is required.")
        if not pid:
            raise ValueError("player_id is required.")
        self.local_facades.append(LocalPlayerFacade(facade_id=key, player_id=pid))
        self.command_channel.subscribe(key, lambda _message: None)

    def stop(self) -> None:
        self._running = False

    def is_driver_managed_setup_phase(self) -> bool:
        if not self.game.is_in_setup_phase():
            return False
        return self.game.get_current_setup_phase() in _DRIVER_MANAGED_SETUP_PHASES

    def run_setup_autosteps(self) -> None:
        if not self.is_driver_managed_setup_phase():
            return
        self._run_coro_sync(self._session_driver.run_setup_sequence())

    def _run_coro_sync(self, coro) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        raise RuntimeError("LocalAuthoritativeRuntime sync helper called while event loop is running.")

    async def _apply_command_default(self, command: GameCommand):
        return await self._apply_command_with_broadcast(command, True)

    async def _apply_command_with_broadcast(self, command: GameCommand, broadcast: bool):
        result = self.game.apply_command(command)
        if bool(getattr(result, "ok", True)) and bool(broadcast):
            await self.command_channel.broadcast(command)
        return result

    def _submit_local_command(self, command: GameCommand) -> CommandResult:
        result = self.game.apply_command(command)
        if bool(getattr(result, "ok", True)):
            self._run_coro_sync(self.command_channel.broadcast(command))
        return result

    def _submit_local_decision_request(self, request) -> None:
        queue_fn = getattr(self.game, "request_decision", None)
        if not callable(queue_fn):
            raise RuntimeError("Game missing request_decision.")
        queue_fn(request)

    def _default_choose_random_mission(self, game: Game) -> tuple[dict, int]:
        combos = iter_mission_combinations()
        if not combos:
            raise RuntimeError("No mission combinations available for random selection.")
        with game_context(game), roll_context("mission_selection"):
            combo_index = max(1, int(get_dice_roll(len(combos)))) - 1
            combo_index = min(combo_index, len(combos) - 1)
            combo = combos[combo_index]
            layouts = list(combo.get("layouts", []) or [])
            if not layouts:
                raise RuntimeError("Selected mission combination has no layouts.")
            layout_index = max(1, int(get_dice_roll(len(layouts)))) - 1
            layout_index = min(layout_index, len(layouts) - 1)
            layout = layouts[layout_index]
        return combo, int(layout)

    async def _queue_formation_decisions(self):
        return []

    def _pending_formation_decisions(self):
        queue = getattr(self.game, "decision_queue", None)
        if queue is None or not hasattr(queue, "list"):
            return []
        return list(queue.list() or [])

    async def _wait_for_formation_decisions(self):
        return None

    async def _broadcast_resync_all(self, _reason: str):
        return None

    def _set_formation_buffering(self, value: bool) -> None:
        self._formation_buffering = bool(value)
