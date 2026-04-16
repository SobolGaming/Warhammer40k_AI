from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.reserve_entry_rules import (
    can_place_unit_arriving_from_reserves,
    evaluate_reserves_arrival_positions,
)
from warhammer40k_ai.engine.ruleset import RulesetBundle


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


class _PlayerStub:
    def __init__(self, player_id: str) -> None:
        self.id = player_id
        self.game = None


class _ArmyStub:
    def __init__(self, player: _PlayerStub | None = None) -> None:
        self.player = player
        self.units: list[object] = []


class _UnitStub:
    def __init__(self, unit_id: str, *, army: _ArmyStub | None = None, reserve_status: str = "reserves") -> None:
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


class _GameStub:
    def __init__(self, arriving: _UnitStub, enemy: _UnitStub, *, preview: bool) -> None:
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

    def get_enemy_units(self, player: _PlayerStub):
        if player is self._arriving.parent_army.player:
            return [self._enemy]
        return [self._arriving]


def _build_game(*, preview: bool) -> tuple[_GameStub, _UnitStub]:
    arriving_player = _PlayerStub("player:arriving")
    enemy_player = _PlayerStub("player:enemy")
    arriving_army = _ArmyStub(arriving_player)
    enemy_army = _ArmyStub(enemy_player)
    arriving = _UnitStub("unit:arriving", army=arriving_army, reserve_status="reserves")
    enemy = _UnitStub("unit:enemy", army=enemy_army, reserve_status="deployed")
    arriving_army.units.append(arriving)
    enemy_army.units.append(enemy)
    enemy.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    game = _GameStub(arriving, enemy, preview=preview)
    return game, arriving


def _model_positions_for(unit: _UnitStub, *, x: float, y: float) -> list[dict]:
    return [
        {
            "model_id": str(unit.models[0].id),
            "position": [float(x), float(y), 0.0],
            "facing": 0.0,
        }
    ]


def test_reserve_entry_helper_uses_current_ingress_distance_by_default() -> None:
    game, arriving = _build_game(preview=False)

    evaluation = evaluate_reserves_arrival_positions(
        game,
        arriving,
        _model_positions_for(arriving, x=19.5, y=10.0),
    )

    assert bool(list(evaluation.get("errors") or [])) is True
    assert 'more than 9"' in str(list(evaluation.get("errors") or [])[0])
    assert can_place_unit_arriving_from_reserves(game, arriving, (19.5, 10.0, 0.0)) is False


def test_preview_reserve_helper_expands_landing_envelope_without_touching_charge_state() -> None:
    game, arriving = _build_game(preview=True)

    evaluation = evaluate_reserves_arrival_positions(
        game,
        arriving,
        _model_positions_for(arriving, x=19.5, y=10.0),
    )

    assert list(evaluation.get("errors") or []) == []
    assert float(evaluation.get("min_enemy_distance", 0.0) or 0.0) == 8.0
    assert can_place_unit_arriving_from_reserves(game, arriving, (19.5, 10.0, 0.0)) is True
    assert arriving.round_state.charge_resolution_choice == {"keep": True}
    assert arriving.round_state.charge_resolution_outcome == {"keep": True}
