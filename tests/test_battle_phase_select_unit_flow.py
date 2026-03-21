from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.decision_requests import (
    build_declare_charge_request,
    build_declare_shots_request,
    build_select_unit_request,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.fight_phase_manager import FightStage
from warhammer40k_ai.engine.game_mixins.phase_handlers_mixin import GamePhaseHandlersMixin


class _DecisionQueueStub:
    def __init__(self) -> None:
        self._requests: list[DecisionRequest] = []

    def list(self):
        return list(self._requests)

    def append(self, request: DecisionRequest) -> None:
        self._requests.append(request)


class _PlayerStub:
    def __init__(self, player_id: str, name: str) -> None:
        self.id = player_id
        self.name = name
        self.army = None

    def get_army(self):
        return self.army


class _ArmyStub:
    def __init__(self, player: _PlayerStub) -> None:
        self.player = player
        self.units = []


class _WargearStub:
    def __init__(self, wargear_id: str) -> None:
        self.id = wargear_id
        self._id = wargear_id

    def is_ranged(self) -> bool:
        return True


class _ModelStub:
    def __init__(self, model_id: str, wargear: _WargearStub) -> None:
        self.id = model_id
        self._id = model_id
        self.wargear = [wargear]
        self.is_alive = True


class _UnitStub:
    def __init__(self, unit_id: str, army: _ArmyStub, *, charge_targets=None) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = f"Unit {unit_id}"
        self.parent_army = army
        self.deployed = True
        self.is_embarked = False
        self.embarked_in = None
        self.is_attached_leader = False
        self.is_joined_support = False
        self.round_state = SimpleNamespace(
            shot_this_round=False,
            fell_back_this_round=False,
            attempted_charge_this_round=False,
            charge_roll=0,
            charge_modifier_choice_pending=False,
            charge_modifier_choice_targets=[],
        )
        self.models = [_ModelStub(f"{unit_id}:model-1", _WargearStub(f"{unit_id}:wg-1"))]
        self._charge_targets = list(charge_targets or [])

    def is_alive(self) -> bool:
        return True

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def is_in_reserves(self) -> bool:
        return False

    def can_declare_charge(self, _game, *, out_of_turn: bool = False) -> bool:
        del out_of_turn
        return bool(self._charge_targets)

    def can_declare_charge_against(self, target, _game, *, out_of_turn: bool = False) -> bool:
        del out_of_turn
        return target in self._charge_targets

    def validate_charge_end_state(self, targets, _game_map):
        return (bool(targets), "")


class _MapStub:
    def __init__(self, enemy_units) -> None:
        self._enemy_units = list(enemy_units or [])

    def get_enemy_units(self, _unit):
        return list(self._enemy_units)

    def get_distance_between_units(self, _lhs, _rhs):
        return 1.0


class _RegistryStub:
    def __init__(self, items) -> None:
        self._items = {str(getattr(item, "id", "")): item for item in list(items or [])}

    def get(self, item_id, *, kind=None):
        del kind
        return self._items.get(str(item_id or ""))


class _FlowGame(GamePhaseHandlersMixin):
    def __init__(self, *, phase_name: str, unit: _UnitStub, enemy_units=None) -> None:
        self.phase = SimpleNamespace(name=phase_name)
        self.turn = 2
        self.is_authoritative = True
        self.decision_queue = _DecisionQueueStub()
        self.queued_requests: list[DecisionRequest] = []
        self.map = _MapStub(enemy_units or [])
        registry_items = [unit]
        registry_items.extend(list(enemy_units or []))
        self.entity_registry = _RegistryStub(registry_items)
        self._player = unit.parent_army.player
        self._opponent = _PlayerStub("player-2", "Opponent")
        self._opponent.army = _ArmyStub(self._opponent)
        self.fight_phase_manager = None

    def get_current_player(self):
        return self._player

    def get_opponent(self):
        return self._opponent

    def _get_player_army(self, player):
        return getattr(player, "army", None)

    def request_decision(self, request: DecisionRequest) -> None:
        self.queued_requests.append(request)
        self.decision_queue.append(request)

    def _resolve_unit_by_id(self, unit_id: str):
        return self.entity_registry.get(unit_id, kind="unit")

    def get_charge_roll_modifiers(self, _unit, *, target_unit=None):
        del target_unit
        return []

    def get_fight_first_units(self, player):
        army = player.get_army()
        return list(getattr(army, "units", []) or [])

    def get_remaining_combatant_units(self, player):
        army = player.get_army()
        return list(getattr(army, "units", []) or [])


def _build_players_with_unit(*, charge_targets=False):
    player = _PlayerStub("player-1", "Player 1")
    army = _ArmyStub(player)
    player.army = army
    enemy_player = _PlayerStub("player-2", "Enemy")
    enemy_army = _ArmyStub(enemy_player)
    enemy_player.army = enemy_army
    enemy_unit = _UnitStub("enemy-1", enemy_army)
    unit = _UnitStub("unit-1", army, charge_targets=[enemy_unit] if charge_targets else [])
    army.units = [unit]
    enemy_army.units = [enemy_unit]
    return player, army, unit, enemy_unit


def test_shooting_phase_selection_request_is_queued() -> None:
    _player, _army, unit, _enemy = _build_players_with_unit()
    game = _FlowGame(phase_name="SHOOTING_PHASE", unit=unit)

    request = game._queue_shooting_phase_selection()

    assert request is not None
    assert request.decision_type == DECISION_SELECT_UNIT
    assert request.context["phase_step"] == "SHOOT_UNITS"
    assert request.context["allowed_unit_ids"] == [unit.id]


def test_shooting_select_unit_resolution_queues_declare_shots_request() -> None:
    _player, _army, unit, _enemy = _build_players_with_unit()
    game = _FlowGame(phase_name="SHOOTING_PHASE", unit=unit)
    request = build_select_unit_request(
        [unit],
        player_id="player-1",
        phase_name="SHOOTING_PHASE",
        phase_step="SHOOT_UNITS",
        selection_purpose="ACTIVATE_SHOOTING_UNIT",
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
    assert queued.decision_type == DECISION_DECLARE_SHOTS
    assert queued.context["unit_id"] == unit.id
    assert queued.context["phase_name"] == "SHOOTING_PHASE"


def test_shooting_followup_requeues_select_unit_after_in_phase_shots() -> None:
    _player, _army, unit, _enemy = _build_players_with_unit()
    game = _FlowGame(phase_name="SHOOTING_PHASE", unit=unit)
    request = build_declare_shots_request(
        unit,
        player_id="player-1",
        out_of_phase=False,
        context={"phase_name": "SHOOTING_PHASE", "phase_step": "SHOOT_UNITS"},
    )
    assert request is not None
    skip_option = next(opt for opt in request.options if opt.payload.get("action") == "skip")
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=skip_option.option_id,
        payload={"skipped": True},
    )

    game._maybe_queue_shooting_phase_followup(request, result)

    assert len(game.queued_requests) == 1
    assert game.queued_requests[0].decision_type == DECISION_SELECT_UNIT


def test_charge_phase_selection_request_is_queued() -> None:
    _player, _army, unit, enemy = _build_players_with_unit(charge_targets=True)
    game = _FlowGame(phase_name="CHARGE_PHASE", unit=unit, enemy_units=[enemy])

    request = game._queue_charge_phase_selection()

    assert request is not None
    assert request.decision_type == DECISION_SELECT_UNIT
    assert request.context["phase_step"] == "DECLARE_CHARGES"
    assert request.context["allowed_unit_ids"] == [unit.id]


def test_charge_select_unit_resolution_queues_declare_charge_request() -> None:
    _player, _army, unit, enemy = _build_players_with_unit(charge_targets=True)
    game = _FlowGame(phase_name="CHARGE_PHASE", unit=unit, enemy_units=[enemy])
    request = build_select_unit_request(
        [unit],
        player_id="player-1",
        phase_name="CHARGE_PHASE",
        phase_step="DECLARE_CHARGES",
        selection_purpose="ACTIVATE_CHARGING_UNIT",
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
    assert queued.decision_type == DECISION_DECLARE_CHARGE
    assert queued.context["unit_id"] == unit.id


def test_charge_followup_queues_charge_move_request_after_declaration() -> None:
    _player, _army, unit, enemy = _build_players_with_unit(charge_targets=True)
    unit.round_state.charge_roll = 8
    game = _FlowGame(phase_name="CHARGE_PHASE", unit=unit, enemy_units=[enemy])
    request = build_declare_charge_request(
        game,
        unit,
        player_id="player-1",
        out_of_turn=False,
        context={"phase_name": "CHARGE_PHASE", "phase_step": "DECLARE_CHARGES"},
    )
    assert request is not None
    option = request.options[0]
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=option.option_id,
        payload={"target_unit_ids": [enemy.id]},
    )

    game._maybe_queue_charge_phase_followup(request, result)

    assert len(game.queued_requests) == 1
    queued = game.queued_requests[0]
    assert queued.decision_type == DECISION_MOVE_UNIT
    assert queued.context["movement_type"] == "charge"
    assert queued.context["target_unit_ids"] == [enemy.id]


def test_charge_move_followup_requeues_select_unit() -> None:
    _player, _army, unit, enemy = _build_players_with_unit(charge_targets=True)
    game = _FlowGame(phase_name="CHARGE_PHASE", unit=unit, enemy_units=[enemy])
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        f"Move {unit.name} (charge)",
        player_id="player-1",
        options=[DecisionOption.create("Confirm", payload={"unit_id": unit.id, "movement_type": "charge"})],
        context={
            "unit_id": unit.id,
            "movement_type": "charge",
            "phase_name": "CHARGE_PHASE",
            "phase_step": "DECLARE_CHARGES",
            "target_unit_ids": [enemy.id],
        },
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=request.options[0].option_id,
        payload={"model_positions": []},
    )

    game._maybe_queue_charge_phase_followup(request, result)

    assert len(game.queued_requests) == 1
    assert game.queued_requests[0].decision_type == DECISION_SELECT_UNIT


def test_fight_phase_selection_request_is_queued_for_stage() -> None:
    _player, _army, unit, _enemy = _build_players_with_unit()
    game = _FlowGame(phase_name="FIGHT_PHASE", unit=unit)

    request = game._queue_fight_phase_selection(
        player=game.get_current_player(),
        eligible_units=[unit],
        stage=FightStage.FIGHT_FIRST,
    )

    assert request is not None
    assert request.decision_type == DECISION_SELECT_UNIT
    assert request.context["phase_step"] == "FIGHT_FIRST"
    assert request.context["allowed_unit_ids"] == [unit.id]


def test_fight_select_unit_resolution_delegates_to_fight_phase_manager() -> None:
    _player, _army, unit, _enemy = _build_players_with_unit()
    game = _FlowGame(phase_name="FIGHT_PHASE", unit=unit)
    calls = []
    game.fight_phase_manager = SimpleNamespace(
        unit_selected=lambda selected_unit, current_player, opponent_player: calls.append(
            (selected_unit, current_player, opponent_player)
        ),
        is_complete=lambda: False,
    )
    request = build_select_unit_request(
        [unit],
        player_id="player-1",
        phase_name="FIGHT_PHASE",
        phase_step="FIGHT_FIRST",
        selection_purpose="ACTIVATE_FIGHTING_UNIT",
        allow_pass=False,
    )
    assert request is not None

    game.on_select_unit_resolved(
        request=request,
        selected_unit_id=unit.id,
        selected_unit=unit,
        payload={"unit_id": unit.id},
        pass_selected=False,
    )

    assert len(calls) == 1
    assert calls[0][0] is unit


def test_fight_followup_resumes_pending_target_selection_after_battle_focus_confirmation() -> None:
    _player, _army, unit, _enemy = _build_players_with_unit()
    game = _FlowGame(phase_name="FIGHT_PHASE", unit=unit)
    resumed = []
    game.fight_phase_manager = SimpleNamespace(
        resume_pending_target_selection=lambda unit_id=None: resumed.append(unit_id),
    )
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Battle Focus",
        player_id="player-1",
        options=[DecisionOption.create("Use", payload={"choice": True})],
        context={"ability": "battle_focus_sudden_strike", "unit_id": unit.id},
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id="player-1",
        option_id=request.options[0].option_id,
        payload={},
    )

    game._maybe_queue_fight_phase_followup(request, result)

    assert resumed == [unit.id]
