from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT, DECISION_SELECT_MOVEMENT_ACTION, DECISION_SELECT_UNIT
from warhammer40k_ai.engine.decision_requests import build_select_movement_action_request, build_select_unit_request
from warhammer40k_ai.engine.game_mixins.phase_handlers_mixin import GamePhaseHandlersMixin
from warhammer40k_ai.engine.decisions import DecisionRequest, DecisionResult
from warhammer40k_ai.units.unit import MovementAction


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


class _ArmyStub:
    def __init__(self, player: _PlayerStub) -> None:
        self.player = player
        self.units = []


class _UnitStub:
    def __init__(self, unit_id: str, army: _ArmyStub) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = f"Unit {unit_id}"
        self.parent_army = army
        self.deployed = True
        self.is_embarked = False
        self.embarked_in = None
        self.is_attached_leader = False
        self.is_joined_support = False
        self.is_transport = False
        self.transport_passengers = []
        self.movement = 6
        self.round_state = SimpleNamespace(
            moved_this_round=False,
            advanced_this_round=False,
            fell_back_this_round=False,
            advance_roll=None,
        )

    def is_alive(self) -> bool:
        return True

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def is_in_reserves(self) -> bool:
        return False

    def get_engagement_state(self, _game_map):
        return SimpleNamespace(value=0)

    def get_available_move_actions(self, _engagement_state):
        return [
            MovementAction.MOVE.value,
            MovementAction.ADVANCE.value,
            MovementAction.REMAIN_STATIONARY.value,
        ]

    def get_phase_movement_distance_bonus(self, _action_type: str, *, game=None):
        del game
        return 0


class _FlowGame(GamePhaseHandlersMixin):
    def __init__(self, unit: _UnitStub) -> None:
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.turn = 2
        self.map = object()
        self.is_authoritative = True
        self.decision_queue = _DecisionQueueStub()
        self.queued_requests: list[DecisionRequest] = []
        self.entity_registry = None
        self._player = unit.parent_army.player
        self._unit = unit

    def get_current_player(self):
        return self._player

    def _get_player_army(self, player):
        return getattr(player, "army", None)

    def request_decision(self, request: DecisionRequest) -> None:
        self.queued_requests.append(request)
        self.decision_queue.append(request)

    def _resolve_unit_by_id(self, unit_id: str):
        return self._unit if str(unit_id or "") == str(self._unit.id) else None


def _build_flow_game():
    player = _PlayerStub("player-1")
    army = _ArmyStub(player)
    player.army = army
    unit = _UnitStub("unit-1", army)
    army.units = [unit]
    return _FlowGame(unit), unit


def test_move_units_selection_request_is_queued_for_authoritative_movement_phase() -> None:
    game, unit = _build_flow_game()

    request = game._queue_movement_phase_move_units_selection()

    assert request is not None
    assert request.decision_type == DECISION_SELECT_UNIT
    assert game.queued_requests == [request]
    assert request.context["phase_step"] == "MOVE_UNITS"
    assert request.context["allowed_unit_ids"] == [unit.id]
    assert request.context["allow_pass"] is False
    assert all(str(option.payload.get("action", "") or "") != "pass" for option in request.options)


def test_select_unit_resolution_queues_select_movement_action_request() -> None:
    game, unit = _build_flow_game()
    request = build_select_unit_request(
        [unit],
        player_id="player-1",
        phase_name="MOVEMENT_PHASE",
        phase_step="MOVE_UNITS",
        selection_purpose="ACTIVATE_MOVEMENT_UNIT",
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
    queued = game.queued_requests[0]
    assert queued.decision_type == DECISION_SELECT_MOVEMENT_ACTION
    assert queued.context["unit_id"] == unit.id


def test_move_units_followup_queues_move_unit_after_move_choice() -> None:
    game, unit = _build_flow_game()
    request = build_select_movement_action_request(
        unit,
        player_id="player-1",
        phase_name="MOVEMENT_PHASE",
        phase_step="MOVE_UNITS",
        selection_purpose="ACTIVATE_MOVEMENT_UNIT",
        game_map=game.map,
    )
    assert request is not None
    move_option = next(opt for opt in request.options if opt.payload.get("action_type") == "move")
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=move_option.option_id,
        payload={},
    )

    game._maybe_queue_movement_phase_move_units_followup(request, result)

    assert len(game.queued_requests) == 1
    queued = game.queued_requests[0]
    assert queued.decision_type == DECISION_MOVE_UNIT
    assert queued.context["movement_type"] == "move"
    assert float(queued.context["max_distance"]) == 6.0


def test_advance_move_request_does_not_reuse_pre_roll_planned_endpoint() -> None:
    game, unit = _build_flow_game()
    unit.round_state.advance_roll = 2
    unit.round_state.planned_movement_type = "advance"
    unit.round_state.planned_movement_distance_inches = 7.0
    unit.round_state.planned_movement_model_positions = [
        {"model_id": "model-1", "position": [7.0, 0.0, 0.0], "facing": 0.0}
    ]

    request = game._queue_move_units_move_request(unit, "advance")

    assert request is not None
    assert request.decision_type == DECISION_MOVE_UNIT
    assert request.context["movement_type"] == "advance"
    assert float(request.context["max_distance"]) == 8.0
    assert "planned_model_positions" not in request.context
    assert "planned_movement_distance_inches" not in request.context


def test_transport_select_movement_action_excludes_embark_and_disembark() -> None:
    game, unit = _build_flow_game()
    unit.is_transport = True
    unit.transport_passengers = [object()]

    request = build_select_movement_action_request(
        unit,
        player_id="player-1",
        phase_name="MOVEMENT_PHASE",
        phase_step="MOVE_UNITS",
        selection_purpose="ACTIVATE_MOVEMENT_UNIT",
        game_map=game.map,
    )

    assert request is not None
    action_types = {str(option.payload.get("action_type", "") or "") for option in request.options}
    assert "move" in action_types
    assert "advance" in action_types
    assert "stationary" in action_types
    assert "embark" not in action_types
    assert "disembark" not in action_types
