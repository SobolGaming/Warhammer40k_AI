from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


class _DummyBase:
    def __init__(self, x: float, y: float, z: float = 0.0, facing: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.facing = facing

    def edge_to_edge_distance(self, _other) -> float:
        return 2.0

    def get_radius(self) -> float:
        return 1.0


class _DummyModel:
    def __init__(self, model_id: str, x: float, y: float) -> None:
        self._id = model_id
        self.model_base = _DummyBase(x, y, 0.0, 0.0)
        self.is_alive = True
        self._movement = 8

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)


class _DummyUnit:
    def __init__(self, unit_id: str) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = "Dummy Unit"
        self.deployed = True
        self.models = [
            _DummyModel("model-a", 10.0, 10.0),
            _DummyModel("model-b", 11.0, 10.0),
        ]


class _DummyArmy:
    def __init__(self, army_id: str, units: list[object]) -> None:
        self._id = army_id
        self.id = army_id
        self.units = list(units)
        self.player = None

    def set_player(self, player: object) -> None:
        self.player = player


def _build_game_with_unit() -> tuple[Game, Player, _DummyUnit]:
    p1 = Player("P1")
    p2 = Player("P2")
    unit = _DummyUnit("unit-1")
    p1.army = _DummyArmy("army-1", [unit])
    p2.army = _DummyArmy("army-2", [])
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    return game, p1, unit


def _build_move_request(player_id: str, unit_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=player_id,
        options=[
            DecisionOption.create(
                "Confirm",
                payload={"unit_id": unit_id, "movement_type": "move", "action": "confirm"},
            ),
            DecisionOption.create(
                "Skip",
                payload={"unit_id": unit_id, "movement_type": "move", "action": "skip"},
            ),
        ],
        context={
            "unit_id": unit_id,
            "movement_type": "move",
            "decision_seed": 42,
            "movement_intent": {
                "objective_targets": ["obj-1"],
                "screen_deny_targets": ["lane-a"],
                "weights": {
                    "screen_coverage": 0.55,
                    "coherency": 0.2,
                    "threat_avoid": 0.15,
                    "obj_proximity": 0.1,
                },
            },
        },
    )


def _normalized_candidate_view(request: DecisionRequest) -> list[tuple[str, dict, dict]]:
    normalized = []
    for candidate in list(request.candidates or []):
        metadata = dict(candidate.metadata or {})
        metadata.pop("solver_ms", None)
        normalized.append((str(candidate.action_id), dict(candidate.params or {}), metadata))
    return normalized


def test_move_candidates_include_path_witness_ref_and_metadata() -> None:
    game, player, unit = _build_game_with_unit()
    request = _build_move_request(player.id, unit.id)
    game.request_decision(request)

    assert "movement_intent" in request.context
    move_candidates = [c for c in list(request.candidates or []) if c.metadata.get("candidate_kind") == "move"]
    assert len(move_candidates) == 1
    witness_ref = move_candidates[0].metadata.get("path_witness_ref")
    assert str(witness_ref).startswith("pathwitness://")
    assert game.path_witness_store.get(witness_ref) is not None


def test_move_candidates_are_deterministic_for_same_intent_and_seed() -> None:
    game, player, unit = _build_game_with_unit()
    first = _build_move_request(player.id, unit.id)
    second = _build_move_request(player.id, unit.id)
    game.request_decision(first)
    game.request_decision(second)

    assert _normalized_candidate_view(first) == _normalized_candidate_view(second)
