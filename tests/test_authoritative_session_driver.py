import asyncio

from warhammer40k_ai.engine.authoritative_session_driver import AuthoritativeSessionDriver
from warhammer40k_ai.engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_SELECT_MISSION,
)
from warhammer40k_ai.engine.phase import SetupPhase


class _FakeGame:
    def __init__(self) -> None:
        self._phases = [
            SetupPhase.MUSTER_ARMIES,
            SetupPhase.SELECT_MISSION_OBJECTIVES,
            SetupPhase.CREATE_BATTLEFIELD,
            SetupPhase.DETERMINE_ATTACKER_AND_DEFENDER,
            SetupPhase.DECLARE_BATTLE_FORMATIONS,
        ]
        self._index = 0
        self.setup_complete = False

    def get_current_setup_phase(self) -> SetupPhase:
        return self._phases[self._index]

    def is_in_setup_phase(self) -> bool:
        return self._index < len(self._phases)

    def advance_phase(self) -> None:
        if self._index < len(self._phases):
            self._index += 1


class _Harness:
    def __init__(self, *, pending_formation_count: int) -> None:
        self.game = _FakeGame()
        self.running = True
        self._pending = pending_formation_count
        self.commands: list[tuple[str, bool, dict]] = []
        self.buffering_values: list[bool] = []
        self.resync_reasons: list[str] = []
        self.queue_called = 0
        self.wait_called = 0

        self.driver = AuthoritativeSessionDriver(
            get_game=lambda: self.game,
            is_running=lambda: self.running,
            apply_command=self.apply_command_default,
            apply_command_with_broadcast=self.apply_command_with_broadcast,
            choose_random_mission=self.choose_random_mission,
            queue_formation_decisions=self.queue_formation_decisions,
            pending_formation_decisions=self.pending_formation_decisions,
            wait_for_formation_decisions=self.wait_for_formation_decisions,
            broadcast_resync_all=self.broadcast_resync_all,
            set_formation_buffering=self.set_formation_buffering,
        )

    async def apply_command_default(self, command):
        return await self.apply_command_with_broadcast(command, True)

    async def apply_command_with_broadcast(self, command, broadcast: bool):
        payload = dict(getattr(command, "payload", {}) or {})
        self.commands.append((command.kind, bool(broadcast), payload))
        if command.kind == CMD_ADVANCE_SETUP_PHASE:
            self.game.advance_phase()
        return []

    def choose_random_mission(self, game):
        assert game is self.game
        return ({"name": "take_and_hold"}, 2)

    async def queue_formation_decisions(self):
        self.queue_called += 1
        return []

    def pending_formation_decisions(self):
        if self._pending <= 0:
            return []
        return [object() for _ in range(self._pending)]

    async def wait_for_formation_decisions(self):
        self.wait_called += 1
        self._pending = 0

    async def broadcast_resync_all(self, reason: str):
        self.resync_reasons.append(reason)

    def set_formation_buffering(self, value: bool):
        self.buffering_values.append(bool(value))


def test_driver_sequences_setup_with_buffered_formation_reveal() -> None:
    harness = _Harness(pending_formation_count=2)
    asyncio.run(harness.driver.run_setup_sequence())

    kinds = [kind for kind, _, _ in harness.commands]
    assert kinds == [
        CMD_ADVANCE_SETUP_PHASE,
        CMD_SELECT_MISSION,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
    ]
    assert harness.commands[1][2]["combination"] == {"name": "take_and_hold"}
    assert harness.commands[1][2]["layout"] == 2
    assert harness.commands[-2][1] is False
    assert harness.commands[-1][1] is False
    assert harness.queue_called == 1
    assert harness.wait_called == 1
    assert harness.buffering_values == [True, False]
    assert harness.resync_reasons == ["formation_reveal"]


def test_driver_executes_unbuffered_formation_path_when_no_pending_decisions() -> None:
    harness = _Harness(pending_formation_count=0)
    asyncio.run(harness.driver.run_setup_sequence())

    assert harness.queue_called == 1
    assert harness.wait_called == 0
    assert harness.buffering_values == []
    assert harness.resync_reasons == []
    assert harness.commands[-2][1] is True
    assert harness.commands[-1][1] is True


def test_driver_noops_when_setup_already_complete() -> None:
    harness = _Harness(pending_formation_count=0)
    harness.game.setup_complete = True

    asyncio.run(harness.driver.run_setup_sequence())

    assert harness.commands == []
    assert harness.queue_called == 0
