from __future__ import annotations

from dataclasses import dataclass

import pytest

from warhammer40k_ai.UI.decision_controller import UIDecisionController
from warhammer40k_ai.UI.phases.phase_manager import BattlePhaseHandler
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
    DECISION_DECLARE_MELEE_WEAPONS,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
    DECISION_REQUEST_DICE_ROLL,
    DECISION_SELECT_FIGHT_TARGETS,
    DECISION_SELECT_MOVEMENT_ACTION,
    DECISION_SELECT_UNIT,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.fight_phase_manager import FightStage
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.headless_policy_controller import HeadlessPolicyDecisionController
from warhammer40k_ai.engine.local_runtime import LocalAuthoritativeRuntime
from warhammer40k_ai.engine import turn_manager
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import MovementAction, Unit


class _MockDatasheet:
    def __init__(self, name: str, *, wargear_rows=None, keywords=None) -> None:
        self.name = name
        self.id = name.lower().replace(" ", "_")
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = list(wargear_rows or [])
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        if wargear_rows:
            names = "; ".join(
                str(row.get("name", "") or "").strip()
                for row in list(wargear_rows or [])
                if str(row.get("name", "") or "").strip()
            )
            self.loadout = f"This model is equipped with: {names}."
        else:
            self.loadout = "This model is equipped with: nothing."
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _phase_test_wargear_rows() -> list[dict[str, str]]:
    return [
        {
            "name": "Bolt Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "-1",
            "D": "1",
            "description": "",
        },
        {
            "name": "Chainsword",
            "type": "Melee",
            "range": "Melee",
            "A": "2",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
    ]


def _make_unit(name: str, *, wargear_rows=None, keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, wargear_rows=wargear_rows, keywords=keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.round_state.shot_this_round = False
    unit.round_state.fell_back_this_round = False
    unit.round_state.attempted_charge_this_round = False
    unit.round_state.charge_roll = 0
    unit.round_state.charge_modifier_choice_pending = False
    unit.round_state.charge_modifier_choice_targets = []
    return unit


@dataclass
class _PhaseGameFixture:
    game: Game
    current_player: Player
    opponent_player: Player
    active_unit: Unit
    enemy_unit: Unit


class _RecordingMovementChoiceDialog:
    def __init__(self, choice: str) -> None:
        self.choice = choice

    def show(self, unit, callback, _game_map, decision_request=None):
        assert decision_request is not None
        callback(self.choice)


class _RecordingMovementDialog:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

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


class _RecordingShootingDeclarationDialog:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def show(self, unit, callback, _game_map, _game_view, decision_request=None, **kwargs):
        self.calls.append(
            {
                "unit": unit,
                "callback": callback,
                "decision_request": decision_request,
                "kwargs": kwargs,
            }
        )


class _RecordingChargeDeclarationDialog:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def show(self, unit, callback, _game_map, _game_view, decision_request=None):
        self.calls.append(
            {
                "unit": unit,
                "callback": callback,
                "decision_request": decision_request,
            }
        )


class _DialogManager:
    def open(self, _dialog, modal=True):
        return modal


class _RecordingGameView:
    def __init__(self, game: Game, *, movement_choice: str = "advance") -> None:
        self.game = game
        self.seen_requests: list[tuple[DecisionRequest, object]] = []
        self.movement_choice_dialog = _RecordingMovementChoiceDialog(movement_choice)
        self.individual_model_movement_dialog = _RecordingMovementDialog()
        self.shooting_declaration_dialog = _RecordingShootingDeclarationDialog()
        self.charge_declaration_dialog = _RecordingChargeDeclarationDialog()
        self.dialog_manager = _DialogManager()
        self.selected_unit_for_movement = None
        self.movement_action = None
        self.selected_model_for_movement = None

    def _on_decision_requested(self, *, request=None, game=None, **_kwargs) -> None:
        if request is not None:
            self.seen_requests.append((request, game))

    def _maybe_prompt_battle_focus_move(self, _unit, _choice, callback):
        callback()

    def _maybe_prompt_battle_focus_charge(self, _unit, _target_unit, callback):
        callback()

    def _maybe_prompt_battle_focus_sudden_strike(self, _unit, callback):
        callback()


@pytest.fixture
def build_phase_game():
    def _build(*, enemy_distance: float = 5.0, current_control: PlayerControl = PlayerControl.LOCAL) -> _PhaseGameFixture:
        friendly_army = Army.with_detachment("Test Faction", "Other")
        friendly_army.faction_id = "TF1"
        enemy_army = Army.with_detachment("Enemy Faction", "Other")
        enemy_army.faction_id = "TF2"

        current_player = Player("Player 1", control=current_control, army=friendly_army)
        opponent_player = Player("Player 2", control=PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[current_player, opponent_player])

        active_unit = _make_unit(
            "Alpha",
            wargear_rows=_phase_test_wargear_rows(),
            keywords=["INFANTRY"],
        )
        enemy_unit = _make_unit(
            "Enemy",
            wargear_rows=_phase_test_wargear_rows(),
            keywords=["INFANTRY"],
        )
        friendly_army.add_unit(active_unit)
        enemy_army.add_unit(enemy_unit)

        active_unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
        enemy_unit.models[0].set_location(10.0 + float(enemy_distance), 10.0, 0.0, 0.0)

        game.map.units = [active_unit, enemy_unit]
        game.rebuild_entity_registry()
        game.turn = 1
        game.current_player_index = 0
        game.setup_complete = True
        return _PhaseGameFixture(
            game=game,
            current_player=current_player,
            opponent_player=opponent_player,
            active_unit=active_unit,
            enemy_unit=enemy_unit,
        )

    return _build


def _phase_contract_request(*, player_id: str, phase_name: str, phase_step: str, selection_purpose: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        f"Confirm phase contract for {phase_name}",
        player_id=player_id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={
            "phase_name": phase_name,
            "phase_step": phase_step,
            "selection_purpose": selection_purpose,
        },
    )


def test_real_game_movement_phase_contract_opens_move_dialog(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=5.0)
    fixture.game.phase = BattleRoundPhases.MOVEMENT_PHASE
    select_unit_request = fixture.game._queue_movement_phase_move_units_selection()
    assert select_unit_request is not None

    game_view = _RecordingGameView(fixture.game, movement_choice="advance")
    handler = BattlePhaseHandler(game_view)

    handler._handle_movement_phase_selection(fixture.active_unit)

    pending = list(fixture.game.decision_queue.list() or [])
    assert len(pending) == 1
    move_request = pending[0]
    assert move_request.decision_type == DECISION_MOVE_UNIT
    assert move_request.context["phase_name"] == "MOVEMENT_PHASE"
    assert move_request.context["phase_step"] == "MOVE_UNITS"
    assert len(game_view.individual_model_movement_dialog.calls) == 1
    call = game_view.individual_model_movement_dialog.calls[0]
    assert call["movement_type"] == "advance"
    assert call["kwargs"]["decision_request"] is move_request


def test_real_game_shooting_phase_contract_opens_shooting_dialog(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=5.0)
    fixture.game.phase = BattleRoundPhases.SHOOTING_PHASE
    select_unit_request = fixture.game._queue_shooting_phase_selection()
    assert select_unit_request is not None

    game_view = _RecordingGameView(fixture.game)
    handler = BattlePhaseHandler(game_view)

    handler._handle_shooting_phase_selection(fixture.active_unit)

    pending = list(fixture.game.decision_queue.list() or [])
    assert len(pending) == 1
    declare_request = pending[0]
    assert declare_request.decision_type == DECISION_DECLARE_SHOTS
    assert declare_request.context["phase_name"] == "SHOOTING_PHASE"
    assert declare_request.context["phase_step"] == "SHOOT_UNITS"
    assert len(game_view.shooting_declaration_dialog.calls) == 1
    assert game_view.shooting_declaration_dialog.calls[0]["decision_request"] is declare_request


def test_real_game_charge_phase_contract_opens_charge_dialog(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=5.0)
    fixture.game.phase = BattleRoundPhases.CHARGE_PHASE
    select_unit_request = fixture.game._queue_charge_phase_selection()
    assert select_unit_request is not None

    game_view = _RecordingGameView(fixture.game)
    handler = BattlePhaseHandler(game_view)

    handler._handle_charge_phase_selection(fixture.active_unit)

    pending = list(fixture.game.decision_queue.list() or [])
    assert len(pending) == 1
    declare_request = pending[0]
    assert declare_request.decision_type == DECISION_DECLARE_CHARGE
    assert declare_request.context["phase_name"] == "CHARGE_PHASE"
    assert declare_request.context["phase_step"] == "DECLARE_CHARGES"
    assert len(game_view.charge_declaration_dialog.calls) == 1
    assert game_view.charge_declaration_dialog.calls[0]["decision_request"] is declare_request


def test_real_game_fight_phase_contract_queues_target_request(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=1.5)
    fixture.game.phase = BattleRoundPhases.FIGHT_PHASE
    select_unit_request = fixture.game._queue_fight_phase_selection(
        player=fixture.game.get_current_player(),
        eligible_units=[fixture.active_unit],
        stage=FightStage.REMAINING_COMBATANTS,
    )
    assert select_unit_request is not None

    game_view = _RecordingGameView(fixture.game)
    handler = BattlePhaseHandler(game_view)

    handler._handle_fight_phase_selection(fixture.active_unit)

    pending = list(fixture.game.decision_queue.list() or [])
    assert len(pending) == 1
    target_request = pending[0]
    assert target_request.decision_type == DECISION_SELECT_FIGHT_TARGETS
    assert target_request.context["phase_name"] == "FIGHT_PHASE"
    assert target_request.context["selection_purpose"] == "SELECT_FIGHT_TARGETS"
    assert target_request.context["allowed_target_unit_ids"] == [fixture.enemy_unit.id]


def test_real_game_ui_controller_receives_phase_contract_request(build_phase_game) -> None:
    fixture = build_phase_game()
    fixture.game.phase = BattleRoundPhases.SHOOTING_PHASE
    game_view = _RecordingGameView(fixture.game)
    fixture.game.add_decision_controller(UIDecisionController(game_view))
    request = _phase_contract_request(
        player_id=fixture.current_player.id,
        phase_name="SHOOTING_PHASE",
        phase_step="SHOOT_UNITS",
        selection_purpose="ACTIVATE_SHOOTING_UNIT",
    )

    fixture.game.request_decision(request)

    assert game_view.seen_requests == [(request, fixture.game)]
    assert fixture.game.decision_queue.get(request.decision_id) is request


def test_real_game_headless_controller_resolves_phase_contract_request(build_phase_game) -> None:
    fixture = build_phase_game(current_control=PlayerControl.REMOTE)
    fixture.game.phase = BattleRoundPhases.CHARGE_PHASE
    HeadlessPolicyDecisionController(game=fixture.game, auto_attach=True)
    resolved: list[tuple[DecisionRequest, object]] = []
    fixture.game.event_system.subscribe(
        "decision_resolved",
        lambda request=None, result=None, **_kwargs: resolved.append((request, result)),
        group="test_phase_flow_contracts",
    )
    request = _phase_contract_request(
        player_id=fixture.current_player.id,
        phase_name="CHARGE_PHASE",
        phase_step="DECLARE_CHARGES",
        selection_purpose="ACTIVATE_CHARGING_UNIT",
    )

    fixture.game.request_decision(request)

    assert fixture.game.decision_queue.get(request.decision_id) is None
    assert len(resolved) == 1
    assert resolved[0][0] is request
    assert resolved[0][1].option_id in {option.option_id for option in request.options}


def test_real_game_headless_movement_phase_preserves_decision_chain(build_phase_game) -> None:
    fixture = build_phase_game(current_control=PlayerControl.REMOTE)
    fixture.game.phase = BattleRoundPhases.MOVEMENT_PHASE
    fixture.active_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.ADVANCE.value]
    HeadlessPolicyDecisionController(game=fixture.game, auto_attach=True)

    fixture.game._queue_movement_phase_move_units_selection()

    requested = [
        str((getattr(event, "payload", {}) or {}).get("decision_type", "") or "")
        for event in list(fixture.game.event_log.events or [])
        if str(getattr(event, "event_type", "") or "") == "decision_requested"
    ]
    assert requested == [
        DECISION_SELECT_UNIT,
        DECISION_SELECT_MOVEMENT_ACTION,
        DECISION_REQUEST_DICE_ROLL,
        DECISION_MOVE_UNIT,
    ]
    assert list(fixture.game.decision_queue.list() or []) == []


def test_real_game_headless_movement_phase_continues_after_first_unit(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=24.0, current_control=PlayerControl.REMOTE)
    game = fixture.game
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    second_unit = _make_unit(
        "Beta",
        wargear_rows=_phase_test_wargear_rows(),
        keywords=["INFANTRY"],
    )
    fixture.current_player.army.add_unit(second_unit)
    second_unit.models[0].set_location(10.0, 20.0, 0.0, 0.0)
    game.map.units = [fixture.active_unit, second_unit, fixture.enemy_unit]
    game.rebuild_entity_registry()

    fixture.active_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.MOVE.value]
    second_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.MOVE.value]
    HeadlessPolicyDecisionController(game=game, auto_attach=True)

    game._queue_movement_phase_move_units_selection()

    moved_unit_ids = {
        str((getattr(event, "payload", {}) or {}).get("unit_id", "") or "")
        for event in list(game.event_log.events or [])
        if str(getattr(event, "event_type", "") or "") == "unit_move_ended"
    }
    assert fixture.active_unit.id in moved_unit_ids
    assert second_unit.id in moved_unit_ids
    assert list(game.decision_queue.list() or []) == []


def test_real_game_headless_movement_phase_records_stationary_units(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=24.0, current_control=PlayerControl.REMOTE)
    game = fixture.game
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    second_unit = _make_unit(
        "Beta Stationary",
        wargear_rows=_phase_test_wargear_rows(),
        keywords=["INFANTRY"],
    )
    fixture.current_player.army.add_unit(second_unit)
    second_unit.models[0].set_location(10.0, 20.0, 0.0, 0.0)
    game.map.units = [fixture.active_unit, second_unit, fixture.enemy_unit]
    game.rebuild_entity_registry()

    fixture.active_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.MOVE.value]
    second_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.REMAIN_STATIONARY.value]

    movement_action_resolutions: list[tuple[str, str]] = []

    def _record_movement_action(request=None, result=None, **_kwargs) -> None:
        if str(getattr(request, "decision_type", "") or "") != DECISION_SELECT_MOVEMENT_ACTION:
            return
        option = next(
            (
                candidate
                for candidate in list(getattr(request, "options", []) or [])
                if str(getattr(candidate, "option_id", "") or "") == str(getattr(result, "option_id", "") or "")
            ),
            None,
        )
        payload = dict(getattr(option, "payload", {}) or {}) if option is not None else {}
        movement_action_resolutions.append(
            (
                str(payload.get("unit_id", "") or ""),
                str(payload.get("action_type", "") or ""),
            )
        )

    game.event_system.subscribe(
        "decision_resolved",
        _record_movement_action,
        group="test_phase_flow_contracts",
    )
    HeadlessPolicyDecisionController(game=game, auto_attach=True)

    game._queue_movement_phase_move_units_selection()

    assert (fixture.active_unit.id, "move") in movement_action_resolutions
    assert (second_unit.id, "stationary") in movement_action_resolutions
    assert second_unit.round_state.moved_this_round is True
    assert second_unit.round_state.remained_stationary_this_round is True
    assert list(game.decision_queue.list() or []) == []


def test_movement_phase_next_phase_marks_unselected_stationary_units(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=24.0)
    game = fixture.game
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    fixture.active_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.REMAIN_STATIONARY.value]

    turn_manager.next_phase(game)

    assert game.phase == BattleRoundPhases.SHOOTING_PHASE
    assert fixture.active_unit.round_state.moved_this_round is True
    assert fixture.active_unit.round_state.remained_stationary_this_round is True
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    assert pending[0].decision_type == DECISION_SELECT_UNIT
    assert pending[0].context["phase_name"] == "SHOOTING_PHASE"


def test_movement_phase_next_phase_queues_for_units_that_cannot_remain_stationary(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=24.0)
    game = fixture.game
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    fixture.active_unit.get_available_move_actions = lambda _engagement_state: [MovementAction.MOVE.value]

    turn_manager.next_phase(game)

    pending = list(game.decision_queue.list() or [])
    assert game.phase == BattleRoundPhases.MOVEMENT_PHASE
    assert len(pending) == 1
    assert pending[0].decision_type == DECISION_SELECT_UNIT
    assert pending[0].context["phase_step"] == "MOVE_UNITS"
    assert fixture.active_unit.round_state.moved_this_round is False


def test_reserves_arrival_counts_as_completed_normal_move(build_phase_game) -> None:
    fixture = build_phase_game(enemy_distance=24.0)
    unit = fixture.active_unit
    game = fixture.game
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    unit.deployed = False
    unit.set_reserve_status("reserves")
    unit.round_state.moved_this_round = False
    unit.round_state.reinforced_this_round = False
    unit.round_state.remained_stationary_this_round = True

    assert unit._finalize_reserves_arrival(turn=2, game_map=game.map) is True

    assert unit.deployed is True
    assert unit.reserve_status == "deployed"
    assert unit.arrived_from_reserves_this_turn is True
    assert unit.round_state.reinforced_this_round is True
    assert unit.round_state.moved_this_round is True
    assert unit.round_state.advanced_this_round is False
    assert unit.round_state.fell_back_this_round is False
    assert unit.round_state.remained_stationary_this_round is False
    assert game._movement_phase_move_units_eligible_units(fixture.current_player) == []


@pytest.mark.integration
def test_real_game_headless_successful_charge_completes_fight_phase(build_phase_game, monkeypatch) -> None:
    fixture = build_phase_game(enemy_distance=3.0, current_control=PlayerControl.REMOTE)
    game = fixture.game

    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda *_args, **_kwargs: 6)

    original_synthesize = HeadlessPolicyDecisionController._synthesized_move_model_positions

    def _radius(model) -> float:
        base = getattr(model, "model_base", None)
        if base is None:
            return 0.0
        return float(getattr(base, "get_radius", lambda: 0.0)() or 0.0)

    def _model_position(model, *, x: float | None = None, y: float | None = None, z: float | None = None):
        current = model.get_location()
        return {
            "model_id": model.id,
            "position": [
                float(current[0] if x is None else x),
                float(current[1] if y is None else y),
                float(current[2] if z is None else z),
            ],
            "facing": float(current[3] if len(current) > 3 else 0.0),
        }

    def _headless_positions_for_charge_and_fight(cls, active_game, request, payload):
        ctx = dict(getattr(request, "context", {}) or {})
        movement_type = str(payload.get("movement_type", "") or ctx.get("movement_type", "") or "").strip().lower()
        unit_id = str(payload.get("unit_id", "") or ctx.get("unit_id", "") or "").strip()
        unit = active_game._resolve_unit_by_id(unit_id) if unit_id else None
        if unit is None or movement_type not in {"charge", "pile_in", "consolidate"}:
            return original_synthesize.__func__(cls, active_game, request, payload)
        model = unit.models[0]
        if movement_type != "charge":
            return [_model_position(model)]
        target_ids = [str(value or "") for value in list(ctx.get("target_unit_ids", []) or []) if str(value or "")]
        target = active_game._resolve_unit_by_id(target_ids[0]) if target_ids else None
        if target is None:
            return None
        target_model = target.models[0]
        target_location = target_model.get_location()
        desired_edge_distance = 0.25
        x = float(target_location[0]) - (_radius(model) + _radius(target_model) + desired_edge_distance)
        return [_model_position(model, x=x, y=float(target_location[1]), z=float(target_location[2]))]

    monkeypatch.setattr(
        HeadlessPolicyDecisionController,
        "_synthesized_move_model_positions",
        classmethod(_headless_positions_for_charge_and_fight),
    )

    HeadlessPolicyDecisionController(game=game, auto_attach=True)

    game.phase = BattleRoundPhases.CHARGE_PHASE
    charge_selection = game._queue_charge_phase_selection(player=fixture.current_player)

    assert charge_selection is not None
    assert bool(getattr(fixture.active_unit.round_state, "charged_this_round", False))
    assert fixture.active_unit.round_state.charge_move_target_ids == {fixture.enemy_unit.id}
    assert bool(getattr(fixture.enemy_unit.round_state, "was_charged_this_round", False))

    game.phase = BattleRoundPhases.FIGHT_PHASE
    manager = game._ensure_fight_phase_manager_started()

    assert manager is not None
    assert manager.is_complete()
    assert bool(getattr(fixture.active_unit.round_state, "fought_this_phase", False))
    assert list(game.decision_queue.list() or []) == []

    requested = [
        str((getattr(event, "payload", {}) or {}).get("decision_type", "") or "")
        for event in list(game.event_log.events or [])
        if str(getattr(event, "event_type", "") or "") == "decision_requested"
    ]
    assert DECISION_SELECT_UNIT in requested
    assert DECISION_DECLARE_CHARGE in requested
    assert DECISION_REQUEST_DICE_ROLL in requested
    assert DECISION_MOVE_UNIT in requested
    assert DECISION_SELECT_FIGHT_TARGETS in requested
    assert DECISION_DECLARE_MELEE_WEAPONS in requested


def test_real_local_runtime_routes_phase_contract_request(build_phase_game) -> None:
    fixture = build_phase_game()
    fixture.game.phase = BattleRoundPhases.MOVEMENT_PHASE
    runtime = LocalAuthoritativeRuntime(fixture.game, manual_phases=True)
    game_view = _RecordingGameView(fixture.game)
    fixture.game.add_decision_controller(UIDecisionController(game_view))
    request = _phase_contract_request(
        player_id=fixture.current_player.id,
        phase_name="MOVEMENT_PHASE",
        phase_step="MOVE_UNITS",
        selection_purpose="ACTIVATE_MOVEMENT_UNIT",
    )

    runtime.game_proxy.request_decision(request)

    assert fixture.game.decision_queue.get(request.decision_id) is request
    assert game_view.seen_requests == [(request, fixture.game)]
