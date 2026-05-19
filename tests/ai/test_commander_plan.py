from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


class _Base:
    x = 0.0
    y = 0.0
    z = 0.0
    facing = 0.0

    def get_radius(self) -> float:
        return 0.5

    def edge_to_edge_distance(self, _other) -> float:
        return 2.0


class _Model:
    def __init__(self, model_id: str, *, movement: int = 6, wounds: int = 1) -> None:
        self._id = model_id
        self._movement = movement
        self.wounds = wounds
        self.is_alive = True
        self.model_base = _Base()

    def get_location(self):
        return (0.0, 0.0, 0.0, 0.0)


class _Unit:
    def __init__(self, unit_id: str, *, movement: int = 6, wounds: int = 1) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.deployed = True
        self.models = [_Model(f"{unit_id}:model", movement=movement, wounds=wounds)]
        self.parent_army = None

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def is_alive(self) -> bool:
        return True


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
    player = Player("P1")
    opponent = Player("P2")
    fast_unit = _Unit("unit:fast", movement=12)
    slow_unit = _Unit("unit:slow", movement=5)
    target_big = _Unit("target:big", wounds=7)
    target_small = _Unit("target:small", wounds=2)
    player.army = _Army("army:p1", [fast_unit, slow_unit])
    opponent.army = _Army("army:p2", [target_small, target_big])
    player.army.set_player(player)
    opponent.army.set_player(opponent)
    return Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent]), player, fast_unit


def _yes_no_request(player_id: str, unit_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player_id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={"unit_id": unit_id},
    )


def test_battle_round_plan_is_cached_and_serializable() -> None:
    game, player, _unit = _build_game()

    first = game.get_or_create_battle_round_plan(player.id)
    second = game.get_or_create_battle_round_plan(player.id)
    data = first.to_dict()

    assert first is second
    assert data["plan_id"].endswith(":battle_round")
    assert data["priority_targets"][0]["target_unit_id"] == "target:big"
    assert sorted(data["unit_tasks"]) == ["unit:fast", "unit:slow"]
    assert sorted(data["movement_plan"]["unit_positioning_tasks"]) == ["unit:fast", "unit:slow"]
    assert sorted(data["shooting_plan"]["unit_fire_assignments"]) == ["unit:fast", "unit:slow"]
    assert data["invalidation"]["invalidated"] is False


def test_commander_context_attaches_to_unit_scoped_decision() -> None:
    game, player, unit = _build_game()
    request = _yes_no_request(player.id, unit.id)

    game.request_decision(request)

    assert request.context["battle_round_plan_id"].endswith(":battle_round")
    assert "battle_round_plan" not in request.context
    assert request.context["unit_battle_task"]["unit_id"] == unit.id
    assert request.context["commander_movement_task"]["unit_id"] == unit.id
    assert request.context["commander_fire_assignment"]["unit_id"] == unit.id
    assert request.context["commander_charge_assignment"]["unit_id"] == unit.id
    assert request.context["commander_fight_assignment"]["unit_id"] == unit.id


def test_preexisting_full_battle_round_plan_is_stripped_without_audit_payload() -> None:
    game, player, unit = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={
            "unit_id": unit.id,
            "battle_round_plan": {"plan_id": "caller-provided"},
        },
    )

    game.request_decision(request)

    assert request.context["battle_round_plan_id"].endswith(":battle_round")
    assert "battle_round_plan" not in request.context


def test_full_battle_round_plan_attaches_when_request_enables_audit_payload() -> None:
    game, player, unit = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={"unit_id": unit.id, "include_full_battle_round_plan": True},
    )

    game.request_decision(request)

    assert (
        request.context["battle_round_plan"]["plan_id"]
        == request.context["battle_round_plan_id"]
    )


def test_full_battle_round_plan_attaches_when_game_enables_audit_payload() -> None:
    game, player, unit = _build_game()
    game.attach_full_battle_round_plan_context = True
    request = _yes_no_request(player.id, unit.id)

    game.request_decision(request)

    assert (
        request.context["battle_round_plan"]["plan_id"]
        == request.context["battle_round_plan_id"]
    )


def test_command_phase_start_builds_battle_round_plan() -> None:
    player = Player("P1")
    opponent = Player("P2")
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent])

    game.start_command_phase()

    assert game.get_or_create_battle_round_plan(player.id).player_id == player.id


def test_commander_dirty_flags_are_reported_and_attached_to_context() -> None:
    game, player, unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)

    game.event_system.publish("unit_move_ended", unit=unit, action="advance")
    flags = game.get_commander_dirty_flags(player.id)

    assert flags.shooting_plan_dirty is True
    assert flags.charge_plan_dirty is True
    assert flags.recommended_replan_scope() == "shooting_only"

    request = _yes_no_request(player.id, unit.id)
    game.request_decision(request)

    assert request.context["commander_dirty_flags"]["shooting_plan_dirty"] is True
    assert request.context["commander_replan_scope"] == "shooting_only"


def test_phase_end_records_commander_execution_report() -> None:
    game, player, unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)
    game.event_system.publish("charge_move_failed", unit=unit, reason="failed_charge")

    game.event_system.publish("phase_end", player=player, phase=game.phase)
    reports = game.get_commander_phase_reports(player.id)

    assert len(reports) == 1
    report = reports[0].to_dict()
    assert report["status"] == "major_variance"
    assert report["recommended_replan_scope"] == "charge_only"
    assert report["metadata"]["dirty_flags"]["fight_plan_dirty"] is True


def test_unit_destroyed_marks_target_priority_repair_for_relevant_plans() -> None:
    game, player, _unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)
    target = game.players[1].army.units[1]

    game.event_system.publish("unit_destroyed", unit=target)
    flags = game.get_commander_dirty_flags(player.id)

    assert flags.target_priorities_dirty is True
    assert flags.status() == "major_variance"
    assert flags.recommended_replan_scope() == "phase"
