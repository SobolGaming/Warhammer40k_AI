from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.path_witness import (
    build_model_path_witness,
    current_model_positions,
    detect_normal_move_engagement_crossing,
    validate_witness_contiguity,
)
from warhammer40k_ai.roster.player import Player


class _Base:
    def __init__(self, x: float, y: float, z: float = 0.0, facing: float = 0.0, radius: float = 0.5) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.facing = facing
        self._radius = radius

    def get_radius(self) -> float:
        return self._radius

    def edge_to_edge_distance(self, other: "_Base") -> float:
        dx = float(self.x) - float(other.x)
        dy = float(self.y) - float(other.y)
        center = (dx * dx + dy * dy) ** 0.5
        return center - float(self._radius) - float(other._radius)


class _Model:
    def __init__(self, model_id: str, x: float, y: float) -> None:
        self._id = model_id
        self.model_base = _Base(x, y)
        self.is_alive = True
        self._movement = 8

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)


class _Unit:
    def __init__(self, unit_id: str, model: _Model) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.models = [model]
        model.parent_unit = self
        self.deployed = True
        self.parent_army = None

    def get_parent_army(self):
        return self.parent_army


class _Army:
    def __init__(self, army_id: str, units: list[_Unit]) -> None:
        self._id = army_id
        self.id = army_id
        self.units = units
        self.player = None
        for unit in self.units:
            unit.parent_army = self

    def set_player(self, player: Player) -> None:
        self.player = player


def test_path_witness_contiguity_and_final_pose_validation() -> None:
    start_positions = [{"model_id": "m1", "position": [0.0, 0.0, 0.0], "facing": 0.0}]
    end_positions = [{"model_id": "m1", "position": [4.0, 0.0, 0.0], "facing": 0.0}]
    witness = build_model_path_witness(
        model_positions=end_positions,
        movement_type="move",
        start_positions=start_positions,
    )
    assert validate_witness_contiguity(witness, end_positions) == []

    broken = dict(witness)
    broken["models"] = [dict(witness["models"][0])]
    broken["models"][0]["final_pose"] = [5.0, 0.0, 0.0, 0.0]
    errors = validate_witness_contiguity(broken, end_positions)
    assert errors


def test_detect_normal_move_engagement_crossing() -> None:
    start_positions = [{"model_id": "m1", "position": [0.0, 0.0, 0.0], "facing": 0.0, "radius": 0.5}]
    end_positions = [{"model_id": "m1", "position": [4.0, 0.0, 0.0], "facing": 0.0, "radius": 0.5}]
    enemy_bases = [{"x": 2.0, "y": 0.0, "z": 0.0, "radius": 0.5}]
    errors = detect_normal_move_engagement_crossing(
        start_positions=start_positions,
        end_positions=end_positions,
        enemy_bases=enemy_bases,
    )
    assert errors


def test_move_validation_rejects_path_crossing_enemy_engagement() -> None:
    p1 = Player("P1")
    p2 = Player("P2")
    friendly_unit = _Unit("u1", _Model("m1", 0.0, 0.0))
    enemy_unit = _Unit("u2", _Model("em1", 2.0, 0.0))
    p1.army = _Army("a1", [friendly_unit])
    p2.army = _Army("a2", [enemy_unit])
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    game.map.units = [friendly_unit, enemy_unit]

    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=p1.id,
        options=[
            DecisionOption.create("Confirm", payload={"unit_id": friendly_unit.id, "movement_type": "move", "action": "confirm"}),
            DecisionOption.create("Skip", payload={"unit_id": friendly_unit.id, "movement_type": "move", "action": "skip"}),
        ],
        context={"unit_id": friendly_unit.id, "movement_type": "move"},
    )
    game.request_decision(request)
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=p1.id,
        option_id=request.options[0].option_id,
        payload={
            "model_positions": [
                {"model_id": "m1", "position": [4.0, 0.0, 0.0], "facing": 0.0}
            ]
        },
    )
    apply_result = game.resolve_decision(result)
    assert apply_result.ok is False
    assert any("crosses engagement range" in str(err) for err in list(apply_result.errors or ()))
