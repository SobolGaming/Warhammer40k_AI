from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from shapely.geometry import Polygon

from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.battlefield.objective_sites import ObjectiveSite
from warhammer40k_ai.engine.combat_timing import (
    CombatEngagementState,
    bind_charge_move_targets,
    engagement_center_distance,
    engagement_state_for_bases,
)
from warhammer40k_ai.engine.fight_phase_manager import FightPhaseManager
from warhammer40k_ai.engine.reserve_entry_rules import (
    can_place_unit_arriving_from_reserves,
    evaluate_reserves_arrival_positions,
)
from warhammer40k_ai.engine.ruleset import RulesetBundle
from warhammer40k_ai.pathing.api import PathQuery, plan_model_path
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.calcs import MovementType, clear_collision_caches, clear_enemy_model_cache


def _fixture_path() -> Path:
    return Path(__file__).parent / "data" / "combat_preview_golden.json"


class _BaseStub:
    has_circular_base = True

    def __init__(self, *, x: float, y: float, radius: float = 0.5, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self._radius = float(radius)

    def get_radius(self) -> float:
        return self._radius

    def get_longest_radius(self) -> float:
        return self._radius


class _ModelStub:
    def __init__(self, model_id: str, base: _BaseStub) -> None:
        self.id = model_id
        self._id = model_id
        self.model_base = base
        self.is_alive = True
        self.parent_unit = None

    def get_location(self) -> tuple[float, float, float, float]:
        return (float(self.model_base.x), float(self.model_base.y), float(self.model_base.z), 0.0)

    def set_location(self, x: float, y: float, z: float, _facing: float) -> None:
        self.model_base.x = float(x)
        self.model_base.y = float(y)
        self.model_base.z = float(z)


class _ChargeUnitStub:
    def __init__(self, unit_id: str, army: object | None = None) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.parent_army = army
        self.round_state = SimpleNamespace(charge_roll=9)

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def is_alive(self) -> bool:
        return True


class _FightPlayer:
    def __init__(self, player_id: str, name: str) -> None:
        self.id = player_id
        self.name = name
        self.army = None

    def get_army(self):
        return self.army


class _FightArmy:
    def __init__(self, player: _FightPlayer) -> None:
        self.player = player
        self.units: list[object] = []


class _FightMap:
    def __init__(self) -> None:
        self.units: list[object] = []
        self.objectives: list[object] = []
        self.game = None

    def get_enemy_units(self, unit):
        own_army = unit.get_parent_army()
        return [
            other
            for other in list(self.units or [])
            if other is not None and other.get_parent_army() is not own_army and other.is_alive()
        ]

    def is_within_engagement_range(self, source_unit, target_unit) -> bool:
        source_base = source_unit.models[0].model_base
        target_base = target_unit.models[0].model_base
        return (
            engagement_state_for_bases(base_a=source_base, base_b=target_base, context={"rules_bundle_id": "preview-11e-core"})
            is not CombatEngagementState.UNENGAGED
        )


class _FightUnit:
    def __init__(
        self,
        unit_id: str,
        name: str,
        army: _FightArmy,
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
        base = _BaseStub(x=x, y=y, radius=1.0)
        model = _ModelStub(f"{unit_id}:model-1", base)
        model.parent_unit = self
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


class _FightGame:
    def __init__(self) -> None:
        self.ruleset_bundle = RulesetBundle.from_values(core_rules_id="11e_preview")
        self.map = _FightMap()
        self.map.game = self
        self.decision_queue = SimpleNamespace(list=lambda: [])
        self.event_system = None
        self._units_by_id: dict[str, object] = {}

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


class _ReservePlayerStub:
    def __init__(self, player_id: str) -> None:
        self.id = player_id
        self.game = None


class _ReserveArmyStub:
    def __init__(self, player: _ReservePlayerStub | None = None) -> None:
        self.player = player
        self.units: list[object] = []


class _ReserveUnitStub:
    def __init__(self, unit_id: str, *, army: _ReserveArmyStub | None = None, reserve_status: str = "reserves") -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.parent_army = army
        self.reserve_status = reserve_status
        self.deployed = reserve_status == "deployed"
        self.embarked_in = None
        self.is_embarked = False
        self.special_rules: dict[str, object] = {}
        self.round_state = SimpleNamespace(
            charge_roll=7,
            charge_resolution_choice={"keep": True},
            charge_resolution_outcome={"keep": True},
        )
        base = _BaseStub(x=0.0, y=0.0)
        model = _ModelStub(f"{unit_id}:model-1", base)
        model.parent_unit = self
        self.models = [model]

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_models(self):
        return list(self.models)

    def is_in_reserves(self) -> bool:
        return str(self.reserve_status or "").strip().lower() != "deployed"

    def can_arrive_from_reserves(self, _turn: int) -> bool:
        return True

    def is_in_strategic_reserves(self) -> bool:
        return str(self.reserve_status or "").strip().lower() == "strategic_reserves"

    def has_deep_strike(self) -> bool:
        return True

    def is_alive(self) -> bool:
        return True

    def _create_potential_base(
        self,
        x: float,
        y: float,
        z: float,
        _facing: float,
        *,
        model: _ModelStub | None = None,
    ) -> _BaseStub:
        radius = float(model.model_base.get_radius()) if model is not None else 0.5
        return _BaseStub(x=float(x), y=float(y), z=float(z), radius=radius)

    def calculate_model_positions(
        self,
        x: float,
        y: float,
        _game_map: object,
        *,
        avoid_friendly_units: bool,
        boundary_repulsors: object | None = None,
    ) -> list[tuple[float, float, float, float]]:
        del avoid_friendly_units, boundary_repulsors
        return [(float(x), float(y), 0.0, 0.0)]


class _ReserveGameStub:
    def __init__(self, arriving: _ReserveUnitStub, enemy: _ReserveUnitStub, *, preview: bool) -> None:
        self.turn = 2
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        if preview:
            self.ruleset_bundle = RulesetBundle.from_values(core_rules_id="preview-11e-core")
        else:
            self.ruleset_bundle = RulesetBundle.from_values(core_rules_id="10e-current-core")
        self.battlefield = SimpleNamespace(width=60.0, height=44.0)
        self.map = SimpleNamespace(width=60.0, height=44.0, units=[enemy])
        self.players = [arriving.parent_army.player, enemy.parent_army.player]
        self.current_player_index = 0
        self._arriving = arriving
        self._enemy = enemy
        for player in self.players:
            player.game = self

    def get_current_player(self):
        return self.players[self.current_player_index]

    def get_enemy_units(self, player: _ReservePlayerStub):
        if player is self._arriving.parent_army.player:
            return [self._enemy]
        return [self._arriving]


class _MockDatasheet:
    def __init__(self, name: str, model_count: int = 1):
        self.name = name
        self.faction_data = {"name": "TEST"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "1",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _build_charge_snapshot() -> dict[str, object]:
    legal_target = _ChargeUnitStub("enemy-1")
    illegal_target = _ChargeUnitStub("enemy-2")
    game = SimpleNamespace(
        ruleset_bundle=RulesetBundle.from_values(core_rules_id="preview-11e-core"),
        _resolve_unit_by_id=lambda unit_id: {
            "enemy-1": legal_target,
            "enemy-2": illegal_target,
        }.get(unit_id),
    )

    class _ChargingUnit(_ChargeUnitStub):
        def can_declare_charge_against(self, target, _game, *, out_of_turn: bool = False) -> bool:
            del _game, out_of_turn
            return target is legal_target

    charging_unit = _ChargingUnit("charger")
    bind_charge_move_targets(game, charging_unit, ["enemy-1", "enemy-2", "enemy-1"])
    return {
        "selection_window": charging_unit.round_state.charge_resolution_choice["selection_window"],
        "choice_kind": charging_unit.round_state.charge_resolution_choice["choice_kind"],
        "reachable_target_ids": charging_unit.round_state.charge_resolution_choice["reachable_target_ids"],
        "chosen_target_ids": charging_unit.round_state.charge_resolution_choice["chosen_target_ids"],
        "must_end_engaged_with_all_targets": charging_unit.round_state.charge_resolution_outcome[
            "must_end_engaged_with_all_targets"
        ],
        "cannot_end_engaged_with_non_targets": charging_unit.round_state.charge_resolution_outcome[
            "cannot_end_engaged_with_non_targets"
        ],
    }


def _build_fight_game() -> tuple[_FightGame, _FightPlayer, _FightPlayer, _FightArmy, _FightArmy]:
    game = _FightGame()
    player_one = _FightPlayer("player-1", "Player 1")
    player_two = _FightPlayer("player-2", "Player 2")
    army_one = _FightArmy(player_one)
    army_two = _FightArmy(player_two)
    player_one.army = army_one
    player_two.army = army_two
    return game, player_one, player_two, army_one, army_two


def _build_fight_first_snapshot() -> dict[str, object]:
    game, current_player, opponent_player, army_one, army_two = _build_fight_game()
    current_unit = _FightUnit("unit-current", "Current Charger", army_one, x=10.0, y=10.0, charged=True)
    opponent_unit = _FightUnit("unit-opponent", "Opponent Fight First", army_two, x=12.5, y=10.0, fight_first=True)
    army_one.units = [current_unit]
    army_two.units = [opponent_unit]
    game.register_units(current_unit, opponent_unit)

    manager = FightPhaseManager(game)
    manager.on_unit_selection_required = Mock()
    manager._queue_fight_move_request = Mock(return_value=object())
    manager.start_fight_phase(current_player, opponent_player)
    while manager.scheduler is not None and manager.scheduler.state.stage.name in {"PILE_IN_ACTIVE", "PILE_IN_REACTIVE"}:
        pending = dict(manager._pending_fight_sequence or {})
        manager.on_fight_move_resolved(
            unit_id=str(pending.get("fighting_unit_id", "") or ""),
            movement_type="pile_in",
        )

    args = manager.on_unit_selection_required.call_args.args
    return {
        "active_player_id": manager.get_active_player().id,
        "selected_unit_ids": [unit.id for unit in list(args[1] or [])],
    }


def _build_overrun_snapshot() -> dict[str, object]:
    game, current_player, opponent_player, army_one, army_two = _build_fight_game()
    friendly = _FightUnit("unit-friendly", "Friendly", army_one, x=10.0, y=10.0)
    transport = _FightUnit("unit-transport", "Destroyed Transport", army_two, x=12.5, y=10.0)
    army_one.units = [friendly]
    army_two.units = [transport]
    game.register_units(friendly, transport)

    manager = FightPhaseManager(game)
    manager.on_unit_selection_required = Mock()
    manager._queue_fight_move_request = Mock(return_value=object())
    manager.start_fight_phase(current_player, opponent_player)
    while manager.scheduler is not None and manager.scheduler.state.stage.name in {"PILE_IN_ACTIVE", "PILE_IN_REACTIVE"}:
        pending = dict(manager._pending_fight_sequence or {})
        manager.on_fight_move_resolved(
            unit_id=str(pending.get("fighting_unit_id", "") or ""),
            movement_type="pile_in",
        )
    manager._queue_fight_move_request.reset_mock()

    snapshot_entry = manager.scheduler.entry_for(friendly)
    transport.models[0].is_alive = False
    game.map.units = [friendly]
    manager.unit_selected(friendly, current_player, opponent_player)

    return {
        "engaged_at_step_start": snapshot_entry.engaged_at_step_start,
        "overrun_available": snapshot_entry.overrun_available,
        "queued_move_type": manager._queue_fight_move_request.call_args.kwargs["movement_type"],
        "pending_mode": dict(manager._pending_fight_sequence or {}).get("mode"),
    }


def _build_reserve_game(*, preview: bool) -> tuple[_ReserveGameStub, _ReserveUnitStub]:
    arriving_player = _ReservePlayerStub("player:arriving")
    enemy_player = _ReservePlayerStub("player:enemy")
    arriving_army = _ReserveArmyStub(arriving_player)
    enemy_army = _ReserveArmyStub(enemy_player)
    arriving = _ReserveUnitStub("unit:arriving", army=arriving_army, reserve_status="reserves")
    enemy = _ReserveUnitStub("unit:enemy", army=enemy_army, reserve_status="deployed")
    arriving_army.units.append(arriving)
    enemy_army.units.append(enemy)
    enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game = _ReserveGameStub(arriving, enemy, preview=preview)
    return game, arriving


def _reserve_positions_for(unit: _ReserveUnitStub, *, x: float, y: float) -> list[dict[str, object]]:
    return [
        {
            "model_id": str(unit.models[0].id),
            "position": [float(x), float(y), 0.0],
            "facing": 0.0,
        }
    ]


def _make_single_model_unit(name: str, faction: str, x: float, y: float) -> Unit:
    unit = Unit(_MockDatasheet(name, model_count=1))
    unit.deployed = True
    unit.faction = faction
    unit.models[0].set_location(x, y, 0.0, 0.0)
    return unit


def _place_enemy_at_edge_distance(friendly: Unit, enemy_name: str, enemy_faction: str, edge_dist: float) -> Unit:
    friendly_model = friendly.models[0]
    friendly_radius = float(friendly_model.model_base.get_longest_radius())

    enemy = Unit(_MockDatasheet(enemy_name, model_count=1))
    enemy.deployed = True
    enemy.faction = enemy_faction
    enemy_radius = float(enemy.models[0].model_base.get_longest_radius())
    center_dist = friendly_radius + enemy_radius + edge_dist
    enemy.models[0].set_location(friendly_model.model_base.x + center_dist, friendly_model.model_base.y, 0.0, 0.0)
    return enemy


def _consolidate_to_objective_snapshot() -> dict[str, object]:
    clear_enemy_model_cache()
    clear_collision_caches()
    game_map = Map(60, 44)
    friendly = _make_single_model_unit("Friendly", "A", 10.0, 10.0)
    enemy = _place_enemy_at_edge_distance(friendly, "Enemy", "B", edge_dist=6.0)
    game_map.units = [friendly, enemy]
    game_map.objectives = [
        ObjectiveSite.terrain_footprint(
            footprint=Polygon([(12.5, 8.0), (16.5, 8.0), (16.5, 12.0), (12.5, 12.0)])
        )
    ]

    result = plan_model_path(
        PathQuery(
            model=friendly.models[0],
            target=(12.0, 10.0, 0.0),
            movement_type=MovementType.CONSOLIDATE,
            max_distance=3.0,
            game_map=game_map,
        )
    ).to_legacy_dict()
    return {
        "valid": bool(result["valid"]),
        "reason": result.get("reason"),
    }


def _build_snapshot() -> dict[str, object]:
    base_a = _BaseStub(x=10.0, y=10.0)
    base_b = _BaseStub(x=12.5, y=10.0)
    current_reserve_game, current_arriving = _build_reserve_game(preview=False)
    preview_reserve_game, preview_arriving = _build_reserve_game(preview=True)
    current_reserve_eval = evaluate_reserves_arrival_positions(
        current_reserve_game,
        current_arriving,
        _reserve_positions_for(current_arriving, x=19.5, y=10.0),
    )
    preview_reserve_eval = evaluate_reserves_arrival_positions(
        preview_reserve_game,
        preview_arriving,
        _reserve_positions_for(preview_arriving, x=19.5, y=10.0),
    )
    return {
        "engagement": {
            "current_state": engagement_state_for_bases(base_a, base_b).value,
            "preview_state": engagement_state_for_bases(
                base_a,
                base_b,
                context={"rules_bundle_id": "preview-11e-core"},
            ).value,
            "preview_center_distance": engagement_center_distance(
                0.5,
                0.5,
                context={"rules_bundle_id": "preview-11e-core"},
            ),
        },
        "charge_resolution": _build_charge_snapshot(),
        "fight_first_order": _build_fight_first_snapshot(),
        "overrun_transport_pop": _build_overrun_snapshot(),
        "consolidate_objective": _consolidate_to_objective_snapshot(),
        "reserve_entry": {
            "current_errors": list(current_reserve_eval.get("errors") or []),
            "preview_errors": list(preview_reserve_eval.get("errors") or []),
            "preview_min_enemy_distance": float(preview_reserve_eval.get("min_enemy_distance", 0.0) or 0.0),
            "current_legal": can_place_unit_arriving_from_reserves(current_reserve_game, current_arriving, (19.5, 10.0, 0.0)),
            "preview_legal": can_place_unit_arriving_from_reserves(preview_reserve_game, preview_arriving, (19.5, 10.0, 0.0)),
        },
    }


def test_preview_combat_snapshot_matches_golden() -> None:
    expected = json.loads(_fixture_path().read_text(encoding="utf-8"))
    assert _build_snapshot() == expected
