from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from warhammer40k_ai.engine.combat_timing import CombatEngagementState, unit_engagement_state
from warhammer40k_ai.engine.decision_kinds import DECISION_SELECT_UNIT
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager, FightStage
from warhammer40k_ai.engine.fight_scheduler import FightSchedulerStage
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.engine.unit_turn_provenance import (
    PhaseBoundary,
    must_fight_next_status_token,
    set_status_tokens_on_unit,
)
from warhammer40k_ai.utility.model_base import Base, BaseType


class _Player:
    def __init__(self, player_id: str, name: str) -> None:
        self.id = player_id
        self.name = name
        self.army = None

    def get_army(self):
        return self.army


class _Army:
    def __init__(self, player: _Player) -> None:
        self.player = player
        self.units = []


class _Map:
    def __init__(self) -> None:
        self.units = []
        self.objectives = []
        self.game = None

    def get_enemy_units(self, unit):
        own_army = unit.get_parent_army()
        return [
            other
            for other in list(self.units or [])
            if other is not None and other.get_parent_army() is not own_army and other.is_alive()
        ]

    def is_within_engagement_range(self, source_unit, target_unit) -> bool:
        return unit_engagement_state(source_unit, target_unit, game=self.game) is not CombatEngagementState.UNENGAGED


class _Unit:
    def __init__(
        self,
        unit_id: str,
        name: str,
        army: _Army,
        *,
        x: float,
        y: float,
        charged: bool = False,
        fight_first: bool = False,
    ) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = name
        self.parent_army = army
        self.deployed = True
        self.is_embarked = False
        self.embarked_in = None
        self.is_attached_leader = False
        self.is_joined_support = False
        self.round_state = SimpleNamespace(
            charged_this_round=charged,
            declared_charge_this_round=charged,
            attempted_charge_this_round=charged,
            fought_this_phase=False,
        )
        self._fight_first = fight_first
        base = Base(BaseType.CIRCULAR, 1.0)
        base.set_position(x, y, 0.0)
        model = SimpleNamespace(
            id=f"{unit_id}:model-1",
            _id=f"{unit_id}:model-1",
            model_base=base,
            parent_unit=self,
            is_alive=True,
            get_location=lambda: (base.x, base.y, base.z, 0.0),
        )
        self.models = [model]

    def is_alive(self) -> bool:
        return any(bool(getattr(model, "is_alive", False)) for model in list(self.models or []))

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def get_models_for_collision(self):
        return list(self.models)

    def should_fight_first(self) -> bool:
        return bool(self._fight_first or self.round_state.declared_charge_this_round)

    def has_fight_first(self) -> bool:
        return bool(self._fight_first)

    def is_eligible_to_fight(self, game_map) -> bool:
        if self.should_fight_first():
            return True
        return any(game_map.is_within_engagement_range(self, enemy) for enemy in game_map.get_enemy_units(self))


class _Game:
    def __init__(self) -> None:
        self.ruleset_bundle = RulesetBundle.from_values(core_rules_id="11e_preview")
        self.map = _Map()
        self.map.game = self
        self.decision_queue = SimpleNamespace(list=lambda: [])
        self.event_system = None
        self._units_by_id = {}
        self.cleared_fight_requests = []

    def register_units(self, *units) -> None:
        self.map.units = list(units)
        self._units_by_id = {str(getattr(unit, "id", "") or ""): unit for unit in units}

    def _resolve_unit_by_id(self, unit_id: str):
        return self._units_by_id.get(str(unit_id or ""))

    def get_fight_first_units(self, player):
        army = player.get_army()
        return [unit for unit in list(getattr(army, "units", []) or []) if unit.should_fight_first()]

    def get_remaining_combatant_units(self, player):
        army = player.get_army()
        return [
            unit
            for unit in list(getattr(army, "units", []) or [])
            if not unit.should_fight_first() and unit.is_eligible_to_fight(self.map)
        ]

    def _clear_pending_fight_phase_requests(self, *, phase_steps=None, decision_types=None) -> None:
        self.cleared_fight_requests.append(
            {
                "phase_steps": list(phase_steps or []),
                "decision_types": list(decision_types or []),
            }
        )


def _build_preview_game():
    game = _Game()
    player_one = _Player("player-1", "Player 1")
    player_two = _Player("player-2", "Player 2")
    army_one = _Army(player_one)
    army_two = _Army(player_two)
    player_one.army = army_one
    player_two.army = army_two
    return game, player_one, player_two, army_one, army_two


def _resolve_pending_batch_pile_ins(manager: FightPhaseManager) -> None:
    while manager.scheduler is not None and manager.scheduler.state.stage in {
        FightSchedulerStage.PILE_IN_ACTIVE,
        FightSchedulerStage.PILE_IN_REACTIVE,
    }:
        pending = dict(manager._pending_fight_sequence or {})
        unit_id = str(pending.get("fighting_unit_id", "") or "")
        if not unit_id:
            break
        manager.on_fight_move_resolved(unit_id=unit_id, movement_type="pile_in")


def test_preview_fights_first_starts_with_active_player() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    current_unit = _Unit("unit-current", "Current Charger", army_one, x=10.0, y=10.0, charged=True)
    opponent_unit = _Unit("unit-opponent", "Opponent Fight First", army_two, x=12.5, y=10.0, fight_first=True)
    army_one.units = [current_unit]
    army_two.units = [opponent_unit]
    game.register_units(current_unit, opponent_unit)

    manager = FightPhaseManager(game)
    manager.on_unit_selection_required = Mock()
    manager._queue_fight_move_request = Mock(return_value=object())

    manager.start_fight_phase(current_player, opponent_player)
    _resolve_pending_batch_pile_ins(manager)

    assert manager.scheduler is not None
    assert manager.scheduler.state.stage == FightSchedulerStage.FIGHTS_FIRST
    assert manager.get_current_stage() == FightStage.FIGHT_FIRST
    assert manager.get_active_player() is current_player

    args = manager.on_unit_selection_required.call_args.args
    assert args[0] is current_player
    assert args[1] == [current_unit]


def test_stage_completion_clears_stale_stage_select_requests() -> None:
    game, current_player, opponent_player, _army_one, _army_two = _build_preview_game()
    manager = FightPhaseManager(game)
    manager.current_stage = FightStage.FIGHT_FIRST
    manager.scheduler = None

    manager._complete_current_stage(current_player, opponent_player)

    assert {
        "phase_steps": ["FIGHT_FIRST"],
        "decision_types": [DECISION_SELECT_UNIT],
    } in game.cleared_fight_requests


def test_fight_phase_completion_clears_all_pending_fight_requests() -> None:
    game, _current_player, _opponent_player, _army_one, _army_two = _build_preview_game()
    manager = FightPhaseManager(game)

    manager._complete_fight_phase()

    assert {"phase_steps": [], "decision_types": []} in game.cleared_fight_requests


def test_preview_pile_in_stage_pauses_for_move_decision() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    current_unit = _Unit("unit-current", "Current", army_one, x=10.0, y=10.0)
    opponent_unit = _Unit("unit-opponent", "Opponent", army_two, x=12.5, y=10.0)
    army_one.units = [current_unit]
    army_two.units = [opponent_unit]
    game.register_units(current_unit, opponent_unit)

    manager = FightPhaseManager(game)
    manager._queue_fight_move_request = Mock(return_value=object())

    manager.start_fight_phase(current_player, opponent_player)

    assert manager.scheduler is not None
    assert manager.scheduler.state.stage == FightSchedulerStage.PILE_IN_ACTIVE
    assert manager.get_current_stage() == FightStage.PILE_IN_ACTIVE
    assert dict(manager._pending_fight_sequence or {}).get("mode") == "pile_in_batch"
    manager._queue_fight_move_request.assert_called_once()
    assert manager._queue_fight_move_request.call_args.kwargs["movement_type"] == "pile_in"


def test_preview_overrun_entitlement_survives_transport_pop_loss_of_engagement() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    friendly = _Unit("unit-friendly", "Friendly", army_one, x=10.0, y=10.0)
    transport = _Unit("unit-transport", "Destroyed Transport", army_two, x=12.5, y=10.0)
    army_one.units = [friendly]
    army_two.units = [transport]
    game.register_units(friendly, transport)

    manager = FightPhaseManager(game)
    manager.on_unit_selection_required = Mock()
    manager._queue_fight_move_request = Mock(return_value=object())

    manager.start_fight_phase(current_player, opponent_player)
    _resolve_pending_batch_pile_ins(manager)
    manager._queue_fight_move_request.reset_mock()

    assert manager.scheduler is not None
    assert manager.scheduler.state.stage == FightSchedulerStage.REMAINING_COMBATANTS
    snapshot_entry = manager.scheduler.entry_for(friendly)
    assert snapshot_entry is not None
    assert snapshot_entry.engaged_at_step_start is True
    assert snapshot_entry.overrun_available is True

    transport.models[0].is_alive = False
    game.map.units = [friendly]

    manager.unit_selected(friendly, current_player, opponent_player)

    manager._queue_fight_move_request.assert_called_once()
    assert manager._queue_fight_move_request.call_args.kwargs["movement_type"] == "pile_in"
    assert dict(manager._pending_fight_sequence or {}).get("mode") == "overrun"


def test_preview_attack_completion_hands_off_to_consolidate_batch_stage() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    friendly = _Unit("unit-friendly", "Friendly", army_one, x=10.0, y=10.0)
    enemy = _Unit("unit-enemy", "Enemy", army_two, x=12.5, y=10.0)
    army_one.units = [friendly]
    army_two.units = [enemy]
    game.register_units(friendly, enemy)

    manager = FightPhaseManager(game)
    manager._queue_fight_move_request = Mock(return_value=object())

    manager.start_fight_phase(current_player, opponent_player)
    _resolve_pending_batch_pile_ins(manager)
    manager._queue_fight_move_request.reset_mock()
    manager.scheduler.queue_consolidate(friendly)

    manager._complete_current_stage(current_player, opponent_player)

    assert manager.get_current_stage() == FightStage.CONSOLIDATE_BATCH
    manager._queue_fight_move_request.assert_called_once()
    assert manager._queue_fight_move_request.call_args.kwargs["movement_type"] == "consolidate"


def test_attack_selection_with_no_targets_marks_unit_fought_and_advances() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    game.ruleset_bundle = RulesetBundle.from_values(core_rules_id="10e-current-core")
    friendly = _Unit("unit-friendly", "Friendly Charger", army_one, x=10.0, y=10.0, charged=True)
    enemy = _Unit("unit-enemy", "Distant Enemy", army_two, x=30.0, y=30.0)
    army_one.units = [friendly]
    army_two.units = [enemy]
    game.register_units(friendly, enemy)

    manager = FightPhaseManager(game)
    manager.start_fight_phase(current_player, opponent_player)

    assert manager.get_current_stage() == FightStage.FIGHT_FIRST
    manager.unit_selected(friendly, current_player, opponent_player)

    assert friendly.round_state.fought_this_phase is True
    assert manager.is_complete()


def test_must_fight_next_status_token_constrains_next_selection() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    current_unit = _Unit("unit-current", "Current", army_one, x=10.0, y=10.0)
    current_other = _Unit("unit-current-other", "Other Current", army_one, x=10.0, y=14.0)
    opponent_unit = _Unit("unit-opponent", "Opponent", army_two, x=12.5, y=10.0)
    opponent_other = _Unit("unit-opponent-other", "Other Opponent", army_two, x=12.5, y=14.0)
    army_one.units = [current_unit, current_other]
    army_two.units = [opponent_unit, opponent_other]
    game.register_units(current_unit, current_other, opponent_unit, opponent_other)
    set_status_tokens_on_unit(
        current_other,
        [
            must_fight_next_status_token(
                unit_id=current_other.id,
                source_id="preview:slaanesh_stratagem",
                expires_at=PhaseBoundary(phase="FIGHT_PHASE"),
                payload={"requires_next_fight_selection": True},
            )
        ],
    )

    manager = FightPhaseManager(game)
    manager.on_unit_selection_required = Mock()
    manager._queue_fight_move_request = Mock(return_value=object())

    manager.start_fight_phase(current_player, opponent_player)
    _resolve_pending_batch_pile_ins(manager)

    args = manager.on_unit_selection_required.call_args.args
    assert manager.scheduler is not None
    assert manager.scheduler.state.stage == FightSchedulerStage.REMAINING_COMBATANTS
    assert manager.get_active_player() is current_player
    assert args[0] is current_player
    assert args[1] == [current_other]


def test_consolidate_batch_decision_context_exposes_categories_and_scheduler_trace() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    friendly = _Unit("unit-friendly", "Friendly", army_one, x=10.0, y=10.0)
    enemy = _Unit("unit-enemy", "Enemy", army_two, x=12.5, y=10.0)
    army_one.units = [friendly]
    army_two.units = [enemy]
    game.register_units(friendly, enemy)

    captured_requests = []
    game.request_decision = captured_requests.append
    manager = FightPhaseManager(game)
    manager._queue_fight_move_request = Mock(wraps=manager._queue_fight_move_request)

    manager.start_fight_phase(current_player, opponent_player)
    _resolve_pending_batch_pile_ins(manager)
    manager.scheduler.queue_consolidate(friendly)
    manager._complete_current_stage(current_player, opponent_player)

    consolidate_request = captured_requests[-1]
    ctx = dict(consolidate_request.context or {})
    assert ctx["fight_move_decision_categories"] == [
        "consolidate_to_engage",
        "consolidate_to_objective",
    ]
    assert ctx["fight_stage_boundary"]["stage"] == "CONSOLIDATE_BATCH"
    assert ctx["fight_scheduler"]["stage_history"]
