from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_RESOLVE_DECISION,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MISSION
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.engine.phase import SetupPhase


class _FakeDecisionQueue:
    def __init__(self) -> None:
        self._requests: dict[str, DecisionRequest] = {}

    def get(self, decision_id: str):
        return self._requests.get(str(decision_id or ""))

    def add(self, request: DecisionRequest) -> None:
        self._requests[str(request.decision_id)] = request

    def pop(self, decision_id: str):
        return self._requests.pop(str(decision_id or ""), None)

    def list(self):
        return list(self._requests.values())


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
        self.mission_request_count = 0

    def is_in_setup_phase(self) -> bool:
        return self._index < len(self._phases)

    def get_current_setup_phase(self) -> SetupPhase:
        return self._phases[self._index]

    def apply_command(self, command):
        payload = dict(getattr(command, "payload", {}) or {})
        self.commands.append((command.kind, payload))
        if command.kind == CMD_ADVANCE_SETUP_PHASE:
            self._index += 1
        if command.kind == CMD_RESOLVE_DECISION:
            self.decision_queue.pop(str(payload.get("decision_id", "") or ""))
        return SimpleNamespace(ok=True)

    def request_mission_selection(self) -> DecisionRequest:
        self.mission_request_count += 1
        existing = [
            req
            for req in list(self.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_MISSION
        ]
        if existing:
            return existing[0]
        combo = {
            "id": "m1",
            "combination_id": "m1",
            "pack_id": "chapter_approved_2025_2026",
            "primary": "p",
            "deployment": "d",
            "layouts": [1],
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_MISSION,
            "Select mission",
            player_id="player-1",
            options=[DecisionOption.create("Mission 1", payload={"combination": combo})],
        )
        self.decision_queue.add(request)
        return request


def test_local_runtime_uses_shared_driver_for_preformation_setup() -> None:
    game = _FakeGame()
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file="army_lists/chaos_test.txt",
        player2_army_file="army_lists/aeldari_test.txt",
        choose_random_mission=lambda _game: ({"id": "m1", "primary": "p", "deployment": "d", "layouts": [1]}, 1),
    )
    mirrored_commands: list[str] = []
    runtime.command_channel.subscribe("tap", lambda message: mirrored_commands.append(getattr(message, "kind", "")))

    runtime.run_setup_autosteps()

    kinds = [kind for kind, _payload in game.commands]
    assert kinds == [
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_RESOLVE_DECISION,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
    ]
    assert game.mission_request_count == 1
    assert game.commands[0][1]["player1_army_file"] == "army_lists/chaos_test.txt"
    assert game.commands[0][1]["player2_army_file"] == "army_lists/aeldari_test.txt"
    assert game.get_current_setup_phase() == SetupPhase.DECLARE_BATTLE_FORMATIONS
    assert mirrored_commands == kinds


def test_local_runtime_driver_managed_phase_predicate() -> None:
    game = _FakeGame()
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file="army_lists/chaos_test.txt",
        player2_army_file="army_lists/aeldari_test.txt",
        choose_random_mission=lambda _game: ({"id": "m1", "primary": "p", "deployment": "d", "layouts": [1]}, 1),
    )

    assert runtime.is_driver_managed_setup_phase() is True
    game._index = 4
    assert runtime.is_driver_managed_setup_phase() is False


def test_local_runtime_registers_two_local_facades() -> None:
    game = _FakeGame()
    runtime = LocalAuthoritativeRuntime(
        game,
        player1_army_file="army_lists/chaos_test.txt",
        player2_army_file="army_lists/aeldari_test.txt",
        choose_random_mission=lambda _game: ({"id": "m1", "primary": "p", "deployment": "d", "layouts": [1]}, 1),
    )
    runtime.register_local_player_facade("local_player1", "p1")
    runtime.register_local_player_facade("local_player2", "p2")

    facade_ids = [entry.facade_id for entry in runtime.local_facades]
    assert facade_ids == ["local_player1", "local_player2"]
