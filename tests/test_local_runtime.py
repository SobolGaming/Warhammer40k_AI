from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_SELECT_MISSION,
)
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.engine.phase import SetupPhase


class _FakeDecisionQueue:
    def list(self):
        return []


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
        self.decision_queue = _FakeDecisionQueue()
        self.commands: list[tuple[str, dict]] = []

    def is_in_setup_phase(self) -> bool:
        return self._index < len(self._phases)

    def get_current_setup_phase(self) -> SetupPhase:
        return self._phases[self._index]

    def apply_command(self, command):
        payload = dict(getattr(command, "payload", {}) or {})
        self.commands.append((command.kind, payload))
        if command.kind == CMD_ADVANCE_SETUP_PHASE:
            self._index += 1
        return SimpleNamespace(ok=True)


def test_local_runtime_uses_shared_driver_for_preformation_setup() -> None:
    game = _FakeGame()
    runtime = LocalAuthoritativeRuntime(
        game,
        choose_random_mission=lambda _game: ({"id": "m1", "primary": "p", "deployment": "d", "layouts": [1]}, 1),
    )
    mirrored_commands: list[str] = []
    runtime.command_channel.subscribe("tap", lambda message: mirrored_commands.append(getattr(message, "kind", "")))

    runtime.run_setup_autosteps()

    kinds = [kind for kind, _payload in game.commands]
    assert kinds == [
        CMD_ADVANCE_SETUP_PHASE,
        CMD_SELECT_MISSION,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
    ]
    assert game.get_current_setup_phase() == SetupPhase.DECLARE_BATTLE_FORMATIONS
    assert mirrored_commands == kinds


def test_local_runtime_driver_managed_phase_predicate() -> None:
    game = _FakeGame()
    runtime = LocalAuthoritativeRuntime(
        game,
        choose_random_mission=lambda _game: ({"id": "m1", "primary": "p", "deployment": "d", "layouts": [1]}, 1),
    )

    assert runtime.is_driver_managed_setup_phase() is True
    game._index = 4
    assert runtime.is_driver_managed_setup_phase() is False


def test_local_runtime_registers_two_local_facades() -> None:
    game = _FakeGame()
    runtime = LocalAuthoritativeRuntime(
        game,
        choose_random_mission=lambda _game: ({"id": "m1", "primary": "p", "deployment": "d", "layouts": [1]}, 1),
    )
    runtime.register_local_player_facade("local_player1", "p1")
    runtime.register_local_player_facade("local_player2", "p2")

    facade_ids = [entry.facade_id for entry in runtime.local_facades]
    assert facade_ids == ["local_player1", "local_player2"]
