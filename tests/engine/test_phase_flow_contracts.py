from __future__ import annotations

from dataclasses import dataclass

import pytest

from warhammer40k_ai.UI.decision_controller import UIDecisionController
from warhammer40k_ai.UI.phases.phase_manager import BattlePhaseHandler
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_CHARGE,
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
