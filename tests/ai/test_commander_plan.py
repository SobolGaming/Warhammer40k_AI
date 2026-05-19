from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


class _Profile:
    def __init__(
        self,
        *,
        range_inches: int = 24,
        attacks: int = 1,
        skill: int = 3,
        strength: int = 4,
        ap: int = 0,
        damage: int = 1,
    ) -> None:
        self.range = SimpleNamespace(max=range_inches)
        self.attacks = attacks
        self.skill = skill
        self.strength = strength
        self.ap = ap
        self.damage = damage


class _Wargear:
    def __init__(self, mode: str, profile: _Profile) -> None:
        self._id = f"wargear:{mode}:{profile.strength}:{profile.damage}:{profile.range.max}"
        self.id = self._id
        self.type = mode
        self.profiles = {"default": profile}

    def is_ranged(self) -> bool:
        return self.type == "ranged"

    def is_melee(self) -> bool:
        return self.type == "melee"


class _Base:
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z
        self.facing = 0.0

    def get_radius(self) -> float:
        return 0.5

    def edge_to_edge_distance(self, other) -> float:
        return float(
            (
                (float(self.x) - float(getattr(other, "x", 0.0))) ** 2
                + (float(self.y) - float(getattr(other, "y", 0.0))) ** 2
                + (float(self.z) - float(getattr(other, "z", 0.0))) ** 2
            )
            ** 0.5
        )


class _Model:
    def __init__(
        self,
        model_id: str,
        *,
        movement: int = 6,
        toughness: int = 4,
        save: int = 3,
        wounds: int = 1,
        objective_control: int = 1,
        wargear: list[_Wargear] | None = None,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        self._id = model_id
        self._movement = movement
        self.movement = movement
        self.toughness = toughness
        self.save = save
        self.wounds = wounds
        self.objective_control = objective_control
        self.is_alive = True
        self.wargear = list(wargear or [])
        self.model_base = _Base(*position)

    def get_location(self):
        return (self.model_base.x, self.model_base.y, self.model_base.z, self.model_base.facing)


class _Unit:
    def __init__(
        self,
        unit_id: str,
        *,
        movement: int = 6,
        toughness: int = 4,
        save: int = 3,
        wounds: int = 1,
        objective_control: int = 1,
        wargear: list[_Wargear] | None = None,
        keywords: list[str] | None = None,
        position: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.deployed = True
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.models = [
            _Model(
                f"{unit_id}:model",
                movement=movement,
                toughness=toughness,
                save=save,
                wounds=wounds,
                objective_control=objective_control,
                wargear=wargear,
                position=position,
            )
        ]
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


def test_commander_analysis_snapshot_is_deterministic_and_bounded() -> None:
    player = Player("P1")
    opponent = Player("P2")
    friendly_units = [_Unit(f"unit:{idx:02d}") for idx in range(30)]
    enemy_units = [
        _Unit(f"target:{idx:02d}", wounds=idx + 1, toughness=4 + idx)
        for idx in range(9)
    ]
    player.army = _Army("army:p1", friendly_units)
    opponent.army = _Army("army:p2", enemy_units)
    player.army.set_player(player)
    opponent.army.set_player(opponent)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent])

    first = game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["analysis_snapshot"]
    second = game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["analysis_snapshot"]

    assert first == second
    assert first["target_count"] == first["limits"]["max_targets"]
    assert first["unit_count"] == first["limits"]["max_units"]
    assert (
        first["unit_target_entry_count"]
        <= first["limits"]["max_units"] * first["limits"]["max_targets_per_unit"]
    )
    assert first["cache_key"]["player_id"] == player.id


def test_commander_analysis_scores_high_wound_targets_above_chaff() -> None:
    game, player, _unit = _build_game()

    snapshot = game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["analysis_snapshot"]
    targets = snapshot["target_analysis"]

    assert targets[0]["target_unit_id"] == "target:big"
    assert targets[0]["threat_score"] > targets[1]["threat_score"]


def test_commander_analysis_prefers_antitank_profile_into_vehicle_target() -> None:
    player = Player("P1")
    opponent = Player("P2")
    anti_tank = _Unit(
        "unit:anti_tank",
        wargear=[
            _Wargear(
                "ranged",
                _Profile(range_inches=48, attacks=2, skill=3, strength=12, ap=-3, damage=6),
            )
        ],
    )
    bolter = _Unit(
        "unit:bolter",
        wargear=[
            _Wargear(
                "ranged",
                _Profile(range_inches=24, attacks=2, skill=3, strength=4, ap=0, damage=1),
            )
        ],
    )
    vehicle = _Unit(
        "target:vehicle",
        toughness=10,
        save=2,
        wounds=12,
        keywords=["VEHICLE"],
        position=(18.0, 0.0, 0.0),
    )
    player.army = _Army("army:p1", [anti_tank, bolter])
    opponent.army = _Army("army:p2", [vehicle])
    player.army.set_player(player)
    opponent.army.set_player(opponent)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent])

    snapshot = game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["analysis_snapshot"]
    by_unit = {
        entry["unit_id"]: entry
        for entry in snapshot["unit_target_matrix"]
        if entry["target_unit_id"] == "target:vehicle"
    }

    assert by_unit["unit:anti_tank"]["expected_shooting_damage"] > by_unit["unit:bolter"]["expected_shooting_damage"]


def test_commander_analysis_records_melee_capability_and_charge_feasibility() -> None:
    player = Player("P1")
    opponent = Player("P2")
    melee_unit = _Unit(
        "unit:melee",
        movement=6,
        wargear=[
            _Wargear(
                "melee",
                _Profile(range_inches=0, attacks=5, skill=3, strength=6, ap=-1, damage=2),
            )
        ],
    )
    target = _Unit("target:nearby", wounds=5, position=(8.0, 0.0, 0.0))
    player.army = _Army("army:p1", [melee_unit])
    opponent.army = _Army("army:p2", [target])
    player.army.set_player(player)
    opponent.army.set_player(opponent)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent])

    snapshot = game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["analysis_snapshot"]
    capability = snapshot["unit_capabilities"]["unit:melee"]
    matrix_entry = snapshot["unit_target_matrix"][0]

    assert capability["melee_capability"] > 0.0
    assert matrix_entry["expected_melee_damage"] > 0.0
    assert matrix_entry["charge_feasibility"] > 0.0


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
