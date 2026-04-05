from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.UI.phases.phase_manager import BattlePhaseHandler
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_SELECT_MOVEMENT_ACTION,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.event.system import EventSystem
from warhammer40k_ai.units.unit import MovementAction


class _DummyGame:
    def __init__(self, with_event_system: bool = True) -> None:
        self.event_system = EventSystem() if with_event_system else None


class _DummyGameView:
    def __init__(self, game) -> None:
        self.game = game


class _DummyDecisionQueue:
    def __init__(self, requests=None):
        self._requests = list(requests or [])

    def list(self):
        return list(self._requests)


class _DummyMovementChoiceDialog:
    def __init__(self, choice: str) -> None:
        self.choice = choice

    def show(self, unit, callback, _game_map, decision_request=None):
        assert decision_request is not None
        callback(self.choice)


class _DummyIndividualModelMovementDialog:
    def __init__(self) -> None:
        self.calls = []

    def show(self, unit, movement_type, callback, _game_map, max_distance, **kwargs):
        self.calls.append(
            {
                "unit": unit,
                "movement_type": movement_type,
                "callback": callback,
                "max_distance": max_distance,
                "kwargs": kwargs,
            }
        )


class _DummyDialogManager:
    def open(self, _dialog, modal=True):
        return modal


class _DummyShootingDeclarationDialog:
    def __init__(self) -> None:
        self.calls = []

    def show(self, unit, callback, _game_map, _game_view, decision_request=None, **kwargs):
        self.calls.append(
            {
                "unit": unit,
                "callback": callback,
                "decision_request": decision_request,
                "kwargs": kwargs,
            }
        )


class _DummyChargeDeclarationDialog:
    def __init__(self) -> None:
        self.calls = []

    def show(self, unit, callback, _game_map, _game_view, decision_request=None):
        self.calls.append(
            {
                "unit": unit,
                "callback": callback,
                "decision_request": decision_request,
            }
        )


class _DummyMap:
    def get_enemy_units(self, _unit):
        return []

    def is_within_engagement_range(self, _unit, _enemy):
        return False


class _DummyMovementGame:
    def __init__(self, *, apply_ok: bool = True, pending_requests=None) -> None:
        self.event_system = None
        self.map = _DummyMap()
        self.decision_queue = _DummyDecisionQueue(pending_requests)
        self._player = SimpleNamespace(id="player-1")
        self.requested_decisions = []
        self.apply_ok = apply_ok
        self.commands = []

    def get_current_player(self):
        return self._player

    def request_decision(self, req):
        self.requested_decisions.append(req)
        return req

    def apply_command(self, _cmd):
        self.commands.append(_cmd)
        return SimpleNamespace(ok=self.apply_ok)


class _DummyMovementGameView:
    def __init__(self, game: _DummyMovementGame, *, choice: str = "advance") -> None:
        self.game = game
        self.movement_choice_dialog = _DummyMovementChoiceDialog(choice)
        self.individual_model_movement_dialog = _DummyIndividualModelMovementDialog()
        self.shooting_declaration_dialog = _DummyShootingDeclarationDialog()
        self.charge_declaration_dialog = _DummyChargeDeclarationDialog()
        self.dialog_manager = _DummyDialogManager()
        self.selected_unit_for_movement = None
        self.movement_action = None
        self.selected_model_for_movement = None

    def _maybe_prompt_battle_focus_move(self, _unit, _choice, callback):
        callback()

    def _maybe_prompt_battle_focus_charge(self, _unit, _target_unit, callback):
        callback()

    def _maybe_prompt_battle_focus_sudden_strike(self, _unit, callback):
        callback()


class _DummyMovementUnit:
    def __init__(self, *, in_reserves: bool = False) -> None:
        self.id = "unit-shalaxi"
        self.name = "Shalaxi Helbane"
        self.parent_army = SimpleNamespace(player=SimpleNamespace(id="player-1"))
        self.is_transport = False
        self.movement = 14
        self._in_reserves = bool(in_reserves)
        wargear = SimpleNamespace(is_ranged=lambda: True, profiles={})
        self.models = [SimpleNamespace(is_alive=True, wargear=[wargear])]
        self.round_state = SimpleNamespace(
            advance_roll=None,
            action_locked_until_turn_end=False,
            shot_this_round=False,
            fell_back_this_round=False,
            attempted_charge_this_round=False,
        )

    def get_engagement_state(self, _game_map):
        return SimpleNamespace(value=0)

    def get_available_move_actions(self, _engagement_state):
        return [
            MovementAction.MOVE.value,
            MovementAction.ADVANCE.value,
            MovementAction.REMAIN_STATIONARY.value,
        ]

    def is_in_reserves(self):
        return self._in_reserves

    def is_alive(self):
        return True

    def get_parent_army(self):
        return self.parent_army

    def can_declare_charge(self, _game, *, out_of_turn: bool = False):
        del out_of_turn
        return True


def _build_pending_movement_choice_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    options = [
        DecisionOption.create("Move", payload={"action_type": "move", "unit_id": unit.id}),
        DecisionOption.create("Advance", payload={"action_type": "advance", "unit_id": unit.id}),
        DecisionOption.create(
            "Remain Stationary",
            payload={"action_type": "stationary", "unit_id": unit.id},
        ),
    ]
    return DecisionRequest.create(
        DECISION_SELECT_MOVEMENT_ACTION,
        f"Select movement action for {unit.name}",
        player_id=player_id,
        options=options,
        context={"unit_id": unit.id},
    )


def _build_pending_select_unit_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Movement Phase / Move Units.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                unit.name,
                payload={"unit_id": unit.id, "action_id": f"{DECISION_SELECT_UNIT}:MOVEMENT_PHASE:MOVE_UNITS:{unit.id}"},
            )
        ],
        context={
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "MOVE_UNITS",
            "selection_purpose": "ACTIVATE_MOVEMENT_UNIT",
            "allow_pass": True,
            "allowed_unit_ids": [unit.id],
        },
    )


def _build_pending_reinforcements_select_unit_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Movement Phase / Reinforcements.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                unit.name,
                payload={"unit_id": unit.id, "action_id": f"{DECISION_SELECT_UNIT}:MOVEMENT_PHASE:REINFORCEMENTS:{unit.id}"},
            )
        ],
        context={
            "phase_name": "MOVEMENT_PHASE",
            "phase_step": "REINFORCEMENTS",
            "selection_purpose": "ACTIVATE_REINFORCEMENT_UNIT",
            "allow_pass": True,
            "allowed_unit_ids": [unit.id],
        },
    )


def _build_pending_reinforcements_move_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        f"Arrive from Reserves: {unit.name}",
        player_id=player_id,
        options=[DecisionOption.create("Confirm", payload={"unit_id": unit.id, "movement_type": "deploy", "action": "confirm"})],
        context={"unit_id": unit.id, "movement_type": "deploy", "placement_kind": "reserves_arrival"},
    )


def _build_pending_shooting_select_unit_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Shooting Phase.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                unit.name,
                payload={"unit_id": unit.id, "action_id": f"{DECISION_SELECT_UNIT}:SHOOTING_PHASE:SHOOT_UNITS:{unit.id}"},
            )
        ],
        context={
            "phase_name": "SHOOTING_PHASE",
            "phase_step": "SHOOT_UNITS",
            "selection_purpose": "ACTIVATE_SHOOTING_UNIT",
            "allow_pass": True,
            "allowed_unit_ids": [unit.id],
        },
    )


def _build_pending_declare_shots_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_DECLARE_SHOTS,
        f"Declare shots for {unit.name}",
        player_id=player_id,
        options=[
            DecisionOption.create("Confirm", payload={"unit_id": unit.id, "action": "confirm"}),
            DecisionOption.create("Skip", payload={"unit_id": unit.id, "action": "skip"}),
        ],
        context={"unit_id": unit.id, "out_of_phase": False},
    )


def _build_pending_charge_select_unit_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Charge Phase.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                unit.name,
                payload={"unit_id": unit.id, "action_id": f"{DECISION_SELECT_UNIT}:CHARGE_PHASE:DECLARE_CHARGES:{unit.id}"},
            )
        ],
        context={
            "phase_name": "CHARGE_PHASE",
            "phase_step": "DECLARE_CHARGES",
            "selection_purpose": "ACTIVATE_CHARGING_UNIT",
            "allow_pass": True,
            "allowed_unit_ids": [unit.id],
        },
    )


def _build_pending_declare_charge_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_DECLARE_CHARGE,
        f"Declare charge for {unit.name}",
        player_id=player_id,
        options=[
            DecisionOption.create("Target", payload={"unit_id": unit.id, "target_unit_id": "enemy-1"}),
        ],
        context={"unit_id": unit.id},
    )


def _build_pending_fight_select_unit_request(unit: _DummyMovementUnit, *, player_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_SELECT_UNIT,
        "Select a unit to act in Fight Phase.",
        player_id=player_id,
        options=[
            DecisionOption.create(
                unit.name,
                payload={"unit_id": unit.id, "action_id": f"{DECISION_SELECT_UNIT}:FIGHT_PHASE:FIGHT_FIRST:{unit.id}"},
            )
        ],
        context={
            "phase_name": "FIGHT_PHASE",
            "phase_step": "FIGHT_FIRST",
            "selection_purpose": "ACTIVATE_FIGHTING_UNIT",
            "allow_pass": False,
            "allowed_unit_ids": [unit.id],
        },
    )


def test_battle_phase_handler_initializes_pending_movement_state() -> None:
    handler = BattlePhaseHandler(_DummyGameView(_DummyGame(with_event_system=False)))

    assert handler._pending_advance_units == set()
    assert handler._pending_move_modifier_actions == {}
    assert handler._pending_pre_move_ability_actions == {}


def test_battle_phase_handler_subscribes_to_roll_made_events() -> None:
    game = _DummyGame(with_event_system=True)
    handler = BattlePhaseHandler(_DummyGameView(game))

    subscribers = list(game.event_system.subscribers.get("roll_made", []))
    assert subscribers
    assert any(
        getattr(callback, "__self__", None) is handler and group == "default"
        for callback, group in subscribers
    )


def test_advance_choice_does_not_create_second_select_movement_decision() -> None:
    unit = _DummyMovementUnit()
    pending_request = _build_pending_movement_choice_request(unit, player_id="player-1")
    game = _DummyMovementGame(apply_ok=True, pending_requests=[pending_request])
    game_view = _DummyMovementGameView(game, choice="advance")
    handler = BattlePhaseHandler(game_view)

    handler._handle_movement_phase_selection(unit)

    assert game.requested_decisions == []
    assert unit.id in handler._pending_advance_units


def test_movement_choice_not_processed_when_resolution_is_rejected() -> None:
    unit = _DummyMovementUnit()
    pending_request = _build_pending_movement_choice_request(unit, player_id="player-1")
    game = _DummyMovementGame(apply_ok=False, pending_requests=[pending_request])
    game_view = _DummyMovementGameView(game, choice="advance")
    handler = BattlePhaseHandler(game_view)
    seen = []
    handler._handle_movement_choice = lambda u, c: seen.append((u, c))

    handler._handle_movement_phase_selection(unit)

    assert game.requested_decisions == []
    assert seen == []


def test_movement_click_resolves_pending_select_unit_before_opening_action_dialog() -> None:
    unit = _DummyMovementUnit()
    select_unit_request = _build_pending_select_unit_request(unit, player_id="player-1")
    movement_request = _build_pending_movement_choice_request(unit, player_id="player-1")
    game = _DummyMovementGame(
        apply_ok=True,
        pending_requests=[select_unit_request, movement_request],
    )
    game_view = _DummyMovementGameView(game, choice="advance")
    handler = BattlePhaseHandler(game_view)

    handler._handle_movement_phase_selection(unit)

    assert game.requested_decisions == []
    assert len(game.commands) == 2
    select_payload = dict(game.commands[0].payload or {})
    movement_payload = dict(game.commands[1].payload or {})
    assert str(select_payload.get("decision_id", "")) == str(select_unit_request.decision_id)
    assert str(movement_payload.get("decision_id", "")) == str(movement_request.decision_id)
    assert unit.id in handler._pending_advance_units


def test_reinforcements_click_resolves_pending_select_unit_before_opening_placement_dialog() -> None:
    unit = _DummyMovementUnit(in_reserves=True)
    select_unit_request = _build_pending_reinforcements_select_unit_request(unit, player_id="player-1")
    move_request = _build_pending_reinforcements_move_request(unit, player_id="player-1")
    game = _DummyMovementGame(
        apply_ok=True,
        pending_requests=[select_unit_request, move_request],
    )
    game_view = _DummyMovementGameView(game, choice="move")
    handler = BattlePhaseHandler(game_view)

    handler._handle_movement_phase_selection(unit)

    assert game.requested_decisions == []
    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("decision_id", "")) == str(select_unit_request.decision_id)
    assert len(game_view.individual_model_movement_dialog.calls) == 1
    call = game_view.individual_model_movement_dialog.calls[0]
    assert call["movement_type"] == "deploy"
    assert call["kwargs"]["decision_request"] is move_request


def test_shooting_click_resolves_pending_select_unit_before_opening_shooting_dialog() -> None:
    unit = _DummyMovementUnit()
    select_unit_request = _build_pending_shooting_select_unit_request(unit, player_id="player-1")
    declare_request = _build_pending_declare_shots_request(unit, player_id="player-1")
    game = _DummyMovementGame(apply_ok=True, pending_requests=[select_unit_request, declare_request])
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    game_view = _DummyMovementGameView(game)
    handler = BattlePhaseHandler(game_view)

    handler._handle_shooting_phase_selection(unit)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("decision_id", "")) == str(select_unit_request.decision_id)
    assert len(game_view.shooting_declaration_dialog.calls) == 1
    assert game_view.shooting_declaration_dialog.calls[0]["decision_request"] is declare_request


def test_charge_click_resolves_pending_select_unit_before_opening_charge_dialog() -> None:
    unit = _DummyMovementUnit()
    select_unit_request = _build_pending_charge_select_unit_request(unit, player_id="player-1")
    declare_request = _build_pending_declare_charge_request(unit, player_id="player-1")
    game = _DummyMovementGame(apply_ok=True, pending_requests=[select_unit_request, declare_request])
    game.phase = SimpleNamespace(name="CHARGE_PHASE")
    game_view = _DummyMovementGameView(game)
    handler = BattlePhaseHandler(game_view)

    handler._handle_charge_phase_selection(unit)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("decision_id", "")) == str(select_unit_request.decision_id)
    assert len(game_view.charge_declaration_dialog.calls) == 1
    assert game_view.charge_declaration_dialog.calls[0]["decision_request"] is declare_request


def test_fight_click_resolves_pending_select_unit_before_direct_fight_activation() -> None:
    unit = _DummyMovementUnit()
    select_unit_request = _build_pending_fight_select_unit_request(unit, player_id="player-1")
    game = _DummyMovementGame(apply_ok=True, pending_requests=[select_unit_request])
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.get_opponent = lambda: SimpleNamespace(id="player-2", name="Opponent")
    game_view = _DummyMovementGameView(game)
    handler = BattlePhaseHandler(game_view)
    selected = []
    handler.fight_phase_manager = SimpleNamespace(
        get_active_player=lambda: unit.get_parent_army().player,
        _get_eligible_units_for_player=lambda _player: [unit],
        unit_selected=lambda selected_unit, _current_player, _opponent_player: selected.append(selected_unit),
    )

    handler._handle_fight_phase_selection(unit)

    assert len(game.commands) == 1
    payload = dict(game.commands[0].payload or {})
    assert str(payload.get("decision_id", "")) == str(select_unit_request.decision_id)
    assert selected == []
