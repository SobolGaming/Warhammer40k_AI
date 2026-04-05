from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


class _Model:
    def __init__(self, model_id: str, movement: int) -> None:
        self._id = model_id
        self._movement = movement
        self.is_alive = True
        self.model_base = type("Base", (), {"x": 0.0, "y": 0.0, "z": 0.0, "facing": 0.0, "radius": (0.5, 0.5), "get_radius": lambda self: 0.5, "edge_to_edge_distance": lambda self, other: 2.0})()

    def get_location(self):
        return (0.0, 0.0, 0.0, 0.0)


class _Unit:
    def __init__(self, unit_id: str, movement: int) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.deployed = True
        self.models = [_Model(f"{unit_id}-m", movement)]
        self.parent_army = None

    def get_parent_army(self):
        return self.parent_army


class _Army:
    def __init__(self, army_id: str, units: list[_Unit]) -> None:
        self._id = army_id
        self.id = army_id
        self.units = list(units)
        self.player = None
        for unit in self.units:
            unit.parent_army = self

    def set_player(self, player: Player) -> None:
        self.player = player


def _build_game() -> tuple[Game, Player, _Unit]:
    p1 = Player("P1")
    p2 = Player("P2")
    fast_unit = _Unit("u-fast", 12)
    slow_unit = _Unit("u-slow", 5)
    p1.army = _Army("a1", [fast_unit, slow_unit])
    p2.army = _Army("a2", [])
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
    return game, p1, fast_unit


def test_tier2_tasks_are_emitted_with_plan() -> None:
    game, player, _fast = _build_game()
    plan = game.get_or_create_tier1_plan(player.id)
    bundle = game.get_or_create_tier2_task_bundle(player.id)

    assert bundle.plan_id == plan.plan_id
    assert bundle.tasks_by_unit_id
    for task in bundle.tasks_by_unit_id.values():
        assert task.movement_intent is not None
        assert task.compute_tier in {"P0", "P1", "P2"}


def test_tier2_compute_tier_maps_to_time_budget_multiplier() -> None:
    game, player, fast_unit = _build_game()
    request = DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Move unit",
        player_id=player.id,
        options=[
            DecisionOption.create("Confirm", payload={"unit_id": fast_unit.id, "movement_type": "move", "action": "confirm"}),
            DecisionOption.create("Skip", payload={"unit_id": fast_unit.id, "movement_type": "move", "action": "skip"}),
        ],
        context={"unit_id": fast_unit.id, "movement_type": "move"},
    )
    game.request_decision(request)
    task = request.context.get("tier2_task", {})
    assert task
    assert request.context["compute_tier"] == task["compute_tier"]
    expected_budget = game.time_manager.get_time_budget_ms(DECISION_MOVE_UNIT, compute_tier=request.context["compute_tier"])
    assert int(request.context["time_budget_ms"]) == expected_budget
