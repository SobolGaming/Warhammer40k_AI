from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_SELECT_UNIT
from warhammer40k_ai.engine.decision_requests import build_select_unit_request
from warhammer40k_ai.engine.decisions import DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game_mixins.setup_deployment_reserves_mixin import GameSetupDeploymentReservesMixin


class _DecisionQueueStub:
    def __init__(self) -> None:
        self._requests: list[DecisionRequest] = []

    def list(self):
        return list(self._requests)

    def append(self, request: DecisionRequest) -> None:
        self._requests.append(request)


class _PlayerStub:
    def __init__(self, player_id: str) -> None:
        self.id = player_id
        self.army = None

    def get_army(self):
        return self.army


class _ArmyStub:
    def __init__(self, player: _PlayerStub) -> None:
        self.player = player
        self.units = []


class _ModelStub:
    def __init__(self, model_id: str) -> None:
        self.id = model_id
        self._id = model_id


class _ReserveUnitStub:
    def __init__(
        self,
        unit_id: str,
        army: _ArmyStub,
        *,
        can_arrive: bool = True,
        must_arrive: bool = False,
        reserve_status: str = "reserves",
        has_deep_strike: bool = True,
        strategic: bool = False,
    ) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = f"Unit {unit_id}"
        self.parent_army = army
        self.deployed = True
        self.reserve_status = "strategic_reserves" if strategic else reserve_status
        self._can_arrive = bool(can_arrive)
        self._must_arrive = bool(must_arrive)
        self._strategic = bool(strategic)
        self._has_deep_strike = bool(has_deep_strike)
        self.is_attached_leader = False
        self.is_joined_support = False
        self.embarked_in = None
        self.is_embarked = False
        self.models = [_ModelStub(f"{unit_id}:model")]

    def is_alive(self) -> bool:
        return True

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def is_in_reserves(self) -> bool:
        return self.reserve_status in {"reserves", "strategic_reserves"}

    def can_arrive_from_reserves(self, _turn: int) -> bool:
        return self._can_arrive

    def must_arrive_from_reserves(self, _turn: int) -> bool:
        return self._must_arrive

    def is_in_strategic_reserves(self) -> bool:
        return self._strategic

    def has_deep_strike(self) -> bool:
        return self._has_deep_strike


class _ReinforcementsGame(GameSetupDeploymentReservesMixin):
    def __init__(self, units: list[_ReserveUnitStub]) -> None:
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.turn = 2
        self.is_authoritative = True
        self.decision_queue = _DecisionQueueStub()
        self.queued_requests: list[DecisionRequest] = []
        self.players = []
        self.reinforcements_step_active = True
        self.reinforcements_step_player_id = "player-1"
        self.reinforcements_step_turn = 2
        self._reinforcements_step_skipped_ids = set()
        player_ids = set()
        for unit in units:
            player = unit.parent_army.player
            if player.id not in player_ids:
                self.players.append(player)
                player_ids.add(player.id)
        self._player = self.players[0]

    def get_current_player(self):
        return self._player

    def request_decision(self, request: DecisionRequest) -> None:
        self.queued_requests.append(request)
        self.decision_queue.append(request)


def _build_reinforcements_game(*, optional_count: int = 1, must_arrive: bool = False):
    player = _PlayerStub("player-1")
    army = _ArmyStub(player)
    player.army = army
    units = []
    for idx in range(optional_count):
        unit = _ReserveUnitStub(f"unit-{idx+1}", army, must_arrive=must_arrive and idx == 0, strategic=idx == 0)
        units.append(unit)
    army.units = units
    return _ReinforcementsGame(units), units


def test_reinforcements_selection_request_is_queued_for_authoritative_step() -> None:
    game, units = _build_reinforcements_game(optional_count=1)

    request = game._queue_movement_phase_reinforcements_selection()

    assert request is not None
    assert request.decision_type == DECISION_SELECT_UNIT
    assert request.context["phase_step"] == "REINFORCEMENTS"
    assert request.context["allow_pass"] is True
    assert request.context["reserve_entry_kinds_by_unit_id"][units[0].id] == "deep_strike"


def test_reinforcements_selection_disallows_pass_when_must_arrive_units_remain() -> None:
    game, units = _build_reinforcements_game(optional_count=2, must_arrive=True)

    request = game._queue_movement_phase_reinforcements_selection()

    assert request is not None
    assert request.context["allow_pass"] is False
    assert request.context["pending_must_arrival_unit_ids"] == [units[0].id]
    assert request.context["allowed_unit_ids"] == [units[0].id]


def test_reinforcements_select_unit_resolution_queues_reserves_move_request() -> None:
    game, units = _build_reinforcements_game(optional_count=1)
    unit = units[0]
    request = build_select_unit_request(
        [unit],
        player_id="player-1",
        phase_name="MOVEMENT_PHASE",
        phase_step="REINFORCEMENTS",
        selection_purpose="ACTIVATE_REINFORCEMENT_UNIT",
        allow_pass=True,
    )
    assert request is not None

    game.on_select_unit_resolved(
        request=request,
        selected_unit_id=unit.id,
        selected_unit=unit,
        payload={"unit_id": unit.id},
        pass_selected=False,
    )

    assert len(game.queued_requests) == 1
    move_request = game.queued_requests[0]
    assert move_request.decision_type == DECISION_MOVE_UNIT
    assert move_request.context["placement_kind"] == "reserves_arrival"
    assert move_request.context["phase_step"] == "REINFORCEMENTS"


def test_reinforcements_skip_requeues_next_available_unit() -> None:
    game, units = _build_reinforcements_game(optional_count=2)
    first_unit, second_unit = units
    move_request = game._build_reserves_arrival_request(first_unit, allow_skip=True)
    assert move_request is not None
    result = DecisionResult(
        decision_id=move_request.decision_id,
        player_id="player-1",
        option_id=move_request.options[-1].option_id,
        payload={"skipped": True},
    )

    game._maybe_queue_movement_phase_reinforcements_followup(move_request, result)

    assert first_unit.id in game._reinforcements_step_skipped_unit_ids_set()
    assert len(game.queued_requests) == 1
    request = game.queued_requests[0]
    assert request.decision_type == DECISION_SELECT_UNIT
    assert request.context["allowed_unit_ids"] == [second_unit.id]
