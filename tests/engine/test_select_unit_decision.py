from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_UNIT
from warhammer40k_ai.engine.decision_requests import (
    _eligible_units_for_move_units_step,
    _eligible_units_for_reinforcements_step,
    build_select_unit_request,
    queue_select_unit_request,
)
from warhammer40k_ai.engine.decisions import DecisionRequest, DecisionResult


class _PlayerStub:
    def __init__(self, player_id: str) -> None:
        self.id = player_id


class _ArmyStub:
    def __init__(self, player: _PlayerStub) -> None:
        self.player = player
        self.units: list[_UnitStub] = []


class _UnitStub:
    def __init__(
        self,
        unit_id: str,
        name: str,
        army: _ArmyStub,
        *,
        root: "_UnitStub | None" = None,
        in_reserves: bool = False,
        embarked: bool = False,
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = name
        self.parent_army = army
        self._root = root if root is not None else self
        self._in_reserves = bool(in_reserves)
        self.is_embarked = bool(embarked)
        self.embarked_in = object() if embarked else None
        self.is_attached_leader = root is not None and root is not self
        self.is_joined_support = False

    def is_alive(self) -> bool:
        return True

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self._root

    def is_in_reserves(self) -> bool:
        return self._in_reserves


class _GameStub:
    def __init__(self, units: list[_UnitStub]) -> None:
        self.players = []
        player_ids: set[str] = set()
        for unit in units:
            player = getattr(unit.parent_army, "player", None)
            if player is not None and str(player.id) not in player_ids:
                self.players.append(player)
                player_ids.add(str(player.id))
        for player in self.players:
            army = None
            for unit in units:
                if getattr(unit.parent_army, "player", None) is player:
                    army = unit.parent_army
                    break
            player.army = army
        self.map = SimpleNamespace(units=list(units))
        self.queued_requests: list[DecisionRequest] = []
        self.select_unit_calls: list[dict] = []

    def request_decision(self, request: DecisionRequest) -> None:
        self.queued_requests.append(request)

    def on_select_unit_resolved(
        self,
        *,
        request: DecisionRequest,
        selected_unit_id: str | None,
        selected_unit: _UnitStub | None,
        payload: dict,
        pass_selected: bool,
    ):
        call = {
            "request": request,
            "selected_unit_id": selected_unit_id,
            "selected_unit": selected_unit,
            "payload": payload,
            "pass_selected": pass_selected,
        }
        self.select_unit_calls.append(call)
        return {
            "selected_unit_id": selected_unit_id,
            "pass_selected": pass_selected,
            "selected_unit_name": getattr(selected_unit, "name", None),
        }


def _build_units():
    player = _PlayerStub("player-1")
    army = _ArmyStub(player)
    root = _UnitStub("unit-1", "Root Unit", army)
    leader = _UnitStub("unit-1-leader", "Leader", army, root=root)
    embarked = _UnitStub("unit-2", "Embarked Unit", army, embarked=True)
    reserve = _UnitStub("unit-3", "Reserve Unit", army, in_reserves=True)
    army.units = [root, leader, embarked, reserve]
    return player, army, root, leader, embarked, reserve


def test_select_unit_request_builder_is_deterministic_and_dedupes_to_roots() -> None:
    _, _, root, leader, embarked, _reserve = _build_units()

    first = build_select_unit_request(
        [leader, embarked, root],
        phase_name="movement_phase",
        phase_step="move_units",
        selection_purpose="activate_movement_unit",
        allow_pass=True,
    )
    second = build_select_unit_request(
        [root, leader, embarked],
        phase_name="movement_phase",
        phase_step="move_units",
        selection_purpose="activate_movement_unit",
        allow_pass=True,
    )

    assert first is not None
    assert second is not None
    assert first.decision_type == DECISION_SELECT_UNIT
    assert first.context["phase_name"] == "MOVEMENT_PHASE"
    assert first.context["phase_step"] == "MOVE_UNITS"
    assert first.context["selection_purpose"] == "ACTIVATE_MOVEMENT_UNIT"
    assert first.context["allowed_unit_ids"] == ["unit-1", "unit-2"]
    assert second.context["allowed_unit_ids"] == ["unit-1", "unit-2"]
    assert [opt.payload.get("action_id") for opt in first.options] == [
        opt.payload.get("action_id") for opt in second.options
    ]
    assert [cand.action_id for cand in first.candidates] == sorted(c.action_id for c in first.candidates)


def test_select_unit_request_labels_duplicate_unit_names_with_roster_ordinals() -> None:
    player = _PlayerStub("player-1")
    army = _ArmyStub(player)
    rangers_1 = _UnitStub("rangers-1", "Rangers", army)
    shroud_runners = _UnitStub("shroud-runners", "Shroud Runners", army)
    rangers_2 = _UnitStub("rangers-2", "Rangers", army)
    rangers_3 = _UnitStub("rangers-3", "Rangers", army)
    army.units = [rangers_1, shroud_runners, rangers_2, rangers_3]

    request = build_select_unit_request(
        [rangers_3, shroud_runners, rangers_2],
        phase_name="movement_phase",
        phase_step="move_units",
        selection_purpose="activate_movement_unit",
    )

    assert request is not None
    labels_by_unit_id = {
        str(option.payload.get("unit_id", "") or ""): str(option.label or "")
        for option in list(request.options or [])
    }
    assert labels_by_unit_id["rangers-2"] == "Rangers #2"
    assert labels_by_unit_id["rangers-3"] == "Rangers #3"
    assert labels_by_unit_id["shroud-runners"] == "Shroud Runners"
    assert request.context["allowed_unit_ids"] == ["rangers-2", "rangers-3", "shroud-runners"]


def test_select_unit_phase_step_helpers_filter_reserves() -> None:
    _, _, root, leader, embarked, reserve = _build_units()

    move_units = _eligible_units_for_move_units_step([leader, reserve, embarked, root])
    reinforcements = _eligible_units_for_reinforcements_step([leader, reserve, embarked, root])

    assert [unit.id for unit in move_units] == ["unit-1", "unit-2"]
    assert [unit.id for unit in reinforcements] == ["unit-3"]


def test_queue_select_unit_request_enqueues_request() -> None:
    _, _, root, _leader, embarked, _reserve = _build_units()
    game = _GameStub([root, embarked])

    request = queue_select_unit_request(
        game,
        [embarked, root],
        phase_name="movement_phase",
        phase_step="move_units",
        selection_purpose="activate_movement_unit",
        allow_pass=False,
    )

    assert request is not None
    assert game.queued_requests == [request]


def test_select_unit_dispatch_calls_game_hook_and_returns_selected_unit() -> None:
    _, _, root, _leader, embarked, _reserve = _build_units()
    game = _GameStub([root, embarked])
    request = build_select_unit_request(
        [embarked, root],
        phase_name="movement_phase",
        phase_step="move_units",
        selection_purpose="activate_movement_unit",
        allow_pass=True,
    )
    assert request is not None
    chosen = next(opt for opt in request.options if opt.payload.get("unit_id") == "unit-2")
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=chosen.option_id,
        payload={"unit_id": "unit-2"},
    )

    apply_result = dispatch_decision(game, request, result)

    assert apply_result.ok is True
    assert apply_result.value == {
        "selected_unit_id": "unit-2",
        "pass_selected": False,
        "selected_unit_name": "Embarked Unit",
    }
    assert game.select_unit_calls
    assert game.select_unit_calls[0]["selected_unit"] is embarked


def test_select_unit_rejects_pass_when_not_allowed() -> None:
    _, _, root, _leader, _embarked, _reserve = _build_units()
    game = _GameStub([root])
    valid_request = build_select_unit_request(
        [root],
        phase_name="movement_phase",
        phase_step="move_units",
        selection_purpose="activate_movement_unit",
        allow_pass=False,
    )
    assert valid_request is not None
    pass_option = type(valid_request.options[0]).create(
        "Pass",
        payload={"action": "pass", "action_id": f"{DECISION_SELECT_UNIT}:MOVEMENT_PHASE:MOVE_UNITS:PASS"},
    )
    request = DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit",
        player_id="player-1",
        options=[valid_request.options[0], pass_option],
        context={"phase_name": "MOVEMENT_PHASE", "phase_step": "MOVE_UNITS", "allow_pass": False},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=pass_option.option_id,
        payload={},
    )

    apply_result = dispatch_decision(game, request, result)

    assert apply_result.ok is False
    assert "pass is not allowed" in " ".join(apply_result.errors).lower()
