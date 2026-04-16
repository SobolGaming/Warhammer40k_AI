from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from warhammer40k_ai.engine.combat_timing import CombatEngagementState, unit_engagement_state
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager, FightStage
from warhammer40k_ai.engine.fight_scheduler import FightSchedulerStage
from warhammer40k_ai.engine.ruleset import RulesetBundle
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


def _build_preview_game():
    game = _Game()
    player_one = _Player("player-1", "Player 1")
    player_two = _Player("player-2", "Player 2")
    army_one = _Army(player_one)
    army_two = _Army(player_two)
    player_one.army = army_one
    player_two.army = army_two
    return game, player_one, player_two, army_one, army_two


def test_preview_fights_first_starts_with_active_player() -> None:
    game, current_player, opponent_player, army_one, army_two = _build_preview_game()
    current_unit = _Unit("unit-current", "Current Charger", army_one, x=10.0, y=10.0, charged=True)
    opponent_unit = _Unit("unit-opponent", "Opponent Fight First", army_two, x=12.5, y=10.0, fight_first=True)
    army_one.units = [current_unit]
    army_two.units = [opponent_unit]
    game.register_units(current_unit, opponent_unit)

    manager = FightPhaseManager(game)
    manager.on_unit_selection_required = Mock()

    manager.start_fight_phase(current_player, opponent_player)

    assert manager.scheduler is not None
    assert manager.scheduler.state.stage == FightSchedulerStage.FIGHTS_FIRST
    assert manager.get_current_stage() == FightStage.FIGHT_FIRST
    assert manager.get_active_player() is current_player

    args = manager.on_unit_selection_required.call_args.args
    assert args[0] is current_player
    assert args[1] == [current_unit]


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
    manager.scheduler.queue_consolidate(friendly)

    manager._complete_current_stage(current_player, opponent_player)

    assert manager.get_current_stage() == FightStage.CONSOLIDATE_BATCH
    manager._queue_fight_move_request.assert_called_once()
    assert manager._queue_fight_move_request.call_args.kwargs["movement_type"] == "consolidate"
