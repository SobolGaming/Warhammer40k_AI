import asyncio

from warhammer40k_ai.engine.authoritative_session_driver import AuthoritativeSessionDriver
from warhammer40k_ai.engine.command_kinds import (
    CMD_ADVANCE_SETUP_PHASE,
    CMD_EXECUTE_SETUP_PHASE,
    CMD_RESOLVE_DECISION,
)
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_MISSION
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
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
        self.mission_request_count = 0

    def get_current_setup_phase(self) -> SetupPhase:
        return self._phases[self._index]

    def is_in_setup_phase(self) -> bool:
        return self._index < len(self._phases)

    def advance_phase(self) -> None:
        if self._index < len(self._phases):
            self._index += 1

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
            "id": "take_and_hold",
            "combination_id": "take_and_hold",
            "pack_id": "chapter_approved_2025_2026",
            "primary": "Take and Hold",
            "deployment": "Crucible of Battle",
            "layouts": [2],
        }
        request = DecisionRequest.create(
            DECISION_CHOOSE_MISSION,
            "Select a mission-pack entry and terrain layout.",
            player_id="player-1",
            options=[DecisionOption.create("Take and Hold", payload={"combination": combo})],
        )
        self.decision_queue.add(request)
        return request


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
        if command.kind == CMD_RESOLVE_DECISION:
            self.game.decision_queue.pop(str(payload.get("decision_id", "") or ""))
        return []

    def choose_random_mission(self, game):
        assert game is self.game
        return (
            {
                "id": "take_and_hold",
                "combination_id": "take_and_hold",
                "pack_id": "chapter_approved_2025_2026",
                "primary": "Take and Hold",
                "deployment": "Crucible of Battle",
                "layouts": [2],
            },
            2,
        )

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
        CMD_RESOLVE_DECISION,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
        CMD_EXECUTE_SETUP_PHASE,
        CMD_ADVANCE_SETUP_PHASE,
    ]
    assert harness.game.mission_request_count == 1
    assert harness.commands[1][2]["result_payload"] == {"layout": 2}
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
