from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CONFIRM_YES_NO,
    DECISION_DISEMBARK,
    DECISION_EMBARK,
)
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
    _next_id = 0

    def __init__(self, mode: str, profile: _Profile) -> None:
        type(self)._next_id += 1
        self._id = f"wargear:{mode}:{profile.strength}:{profile.damage}:{profile.range.max}:{type(self)._next_id}"
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
        self.alive = True
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.is_transport = "TRANSPORT" in {str(keyword).upper() for keyword in self.keywords}
        self.transport_capacity = 10 if self.is_transport else 0
        self.transport_passengers = []
        self.embarked_in = None
        self.reserve_status = "deployed"
        self.round_state = SimpleNamespace(
            embarked_this_round=False,
            disembarked_this_round=False,
        )
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
        return bool(self.alive)

    def can_transport(self, passenger_unit) -> bool:
        return bool(
            self.is_transport
            and passenger_unit is not self
            and not getattr(passenger_unit, "is_transport", False)
        )


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


def _build_custom_game(friendly_units: list[_Unit], enemy_units: list[_Unit]) -> tuple[Game, Player, Player]:
    player = Player("P1")
    opponent = Player("P2")
    player.army = _Army("army:p1", friendly_units)
    opponent.army = _Army("army:p2", enemy_units)
    player.army.set_player(player)
    opponent.army.set_player(opponent)
    return Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent]), player, opponent


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
    assert data["metadata"]["general_plan_id"] == game.get_or_create_general_plan(player.id).plan_id


def test_general_plan_is_cached_serializable_and_has_limited_resource_ledger() -> None:
    game, player, _unit = _build_game()

    first = game.get_or_create_general_plan(player.id)
    second = game.get_or_create_general_plan(player.id)
    data = first.to_dict()

    assert first is second
    assert data["plan_id"] == f"general:{player.id}:game"
    assert data["player_id"] == player.id
    assert sorted(data["battle_round_directives"]) == ["1", "2", "3", "4", "5"]
    assert f"{player.id}:cp_pool" in data["limited_resource_policy"]
    assert f"{player.id}:stratagem_reserve" in data["limited_resource_policy"]
    assert data["resource_ledger"]["resource_count"] >= 2
    assert data["cp_policy"]["reserve_for_interrupt_or_overwatch"] == 1
    assert data["reserve_policy"]["late_game_scoring_preservation"] is True


def test_general_transport_doctrine_records_current_passengers() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_custom_game([transport, passenger], [])

    doctrine = game.get_or_create_general_plan(player.id).to_dict()["transport_policy"]["unit:transport"]

    assert doctrine["doctrine"] == "preserve_and_deliver"
    assert doctrine["passenger_unit_ids"] == ["unit:passenger"]
    assert doctrine["preserve_passengers"] is True
    assert doctrine["post_delivery_role"] == "screen_objective"
    assert doctrine["metadata"]["current_passenger_unit_ids"] == ["unit:passenger"]


def test_commander_transport_plan_keeps_passenger_embarked_before_delivery_round() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_custom_game([transport, passenger], [])
    game.turn = 1

    movement_plan = game.get_or_create_battle_round_plan(player.id).to_dict()["movement_plan"]
    passenger_assignment = movement_plan["transport_assignments"]["unit:passenger"]
    transport_assignment = movement_plan["transport_assignments"]["unit:transport"]

    assert passenger_assignment["intent"] == "stay_embarked"
    assert passenger_assignment["transport_unit_id"] == "unit:transport"
    assert passenger_assignment["desired_round"] == 2
    assert transport_assignment["intent"] == "deliver_to_staging_region"
    assert transport_assignment["destination_region_ids"] == ["midboard_stage"]


def test_commander_transport_plan_disembarks_passenger_on_delivery_round() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_custom_game([transport, passenger], [])
    game.turn = 2

    assignment = game.get_or_create_battle_round_plan(player.id).to_dict()["movement_plan"]["transport_assignments"][
        "unit:passenger"
    ]

    assert assignment["intent"] == "disembark_this_round"
    assert assignment["disembark_trigger"] == "delivery_round"


def test_commander_transport_plan_assigns_embark_after_action_for_planned_rider() -> None:
    rider = _Unit("unit:rider", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    game, player, _opponent = _build_custom_game([transport, rider], [])

    movement_plan = game.get_or_create_battle_round_plan(player.id).to_dict()["movement_plan"]
    rider_assignment = movement_plan["transport_assignments"]["unit:rider"]
    transport_assignment = movement_plan["transport_assignments"]["unit:transport"]

    assert rider_assignment["intent"] == "embark_after_action"
    assert rider_assignment["transport_unit_id"] == "unit:transport"
    assert rider_assignment["embark_trigger"] == "after_unit_action"
    assert transport_assignment["intent"] == "deliver_to_staging_region"


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


def test_greedy_assignment_focuses_multiple_weak_shooters_on_high_threat_target() -> None:
    weak_gun = lambda: _Wargear(
        "ranged",
        _Profile(range_inches=24, attacks=4, skill=3, strength=5, ap=-1, damage=2),
    )
    shooters = [
        _Unit(f"unit:shooter:{idx}", wargear=[weak_gun()])
        for idx in range(3)
    ]
    heavy_target = _Unit("target:heavy", toughness=8, save=3, wounds=12, position=(12.0, 0.0, 0.0))
    backup_target = _Unit("target:backup", toughness=4, save=4, wounds=4, position=(14.0, 0.0, 0.0))
    game, player, _opponent = _build_custom_game(shooters, [backup_target, heavy_target])

    plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    heavy_fire_plan = plan["shooting_plan"]["target_fire_plans"]["target:heavy"]
    assigned_units = heavy_fire_plan["assigned_unit_ids"]

    assert len(assigned_units) >= 2
    for unit_id in assigned_units:
        assert (
            plan["shooting_plan"]["unit_fire_assignments"][unit_id]["primary_target_unit_id"]
            == "target:heavy"
        )


def test_greedy_assignment_overkill_guard_redirects_extra_shooters() -> None:
    strong_gun = lambda: _Wargear(
        "ranged",
        _Profile(range_inches=36, attacks=2, skill=3, strength=12, ap=-4, damage=6),
    )
    shooters = [
        _Unit(f"unit:strong:{idx}", wargear=[strong_gun()])
        for idx in range(2)
    ]
    thin_priority_target = _Unit(
        "target:thin_priority",
        toughness=12,
        save=2,
        wounds=2,
        objective_control=8,
        keywords=["VEHICLE"],
        position=(12.0, 0.0, 0.0),
    )
    secondary_target = _Unit(
        "target:secondary",
        toughness=4,
        save=4,
        wounds=8,
        position=(16.0, 0.0, 0.0),
    )
    game, player, _opponent = _build_custom_game(shooters, [secondary_target, thin_priority_target])

    plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    target_fire_plans = plan["shooting_plan"]["target_fire_plans"]

    assert len(target_fire_plans["target:thin_priority"]["assigned_unit_ids"]) == 1
    assert len(target_fire_plans["target:secondary"]["assigned_unit_ids"]) == 1


def test_greedy_assignment_marks_melee_first_units_for_charge_and_fight() -> None:
    melee_unit = _Unit(
        "unit:melee",
        movement=6,
        wargear=[
            _Wargear(
                "melee",
                _Profile(range_inches=0, attacks=6, skill=3, strength=6, ap=-1, damage=2),
            )
        ],
    )
    target = _Unit("target:charge", wounds=6, position=(8.0, 0.0, 0.0))
    game, player, _opponent = _build_custom_game([melee_unit], [target])

    plan = game.get_or_create_battle_round_plan(player.id).to_dict()

    assert plan["unit_tasks"]["unit:melee"]["role"] == "melee_first"
    assert plan["unit_tasks"]["unit:melee"]["primary_target_unit_id"] == "target:charge"
    assert plan["unit_tasks"]["unit:melee"]["shooting_intent"] == "skip_for_charge"
    assert plan["movement_plan"]["unit_positioning_tasks"]["unit:melee"]["intentionally_accept_shooting_ineligible"] is True
    assert plan["shooting_plan"]["unit_fire_assignments"]["unit:melee"].get("primary_target_unit_id") is None
    assert plan["charge_plan"]["unit_charge_assignments"]["unit:melee"]["primary_target_unit_id"] == "target:charge"
    assert plan["charge_plan"]["unit_charge_assignments"]["unit:melee"]["intentionally_skip_shooting"] is True
    assert plan["fight_plan"]["unit_fight_assignments"]["unit:melee"]["primary_target_unit_id"] == "target:charge"


def test_greedy_assignment_marks_shooting_first_units_for_fire_plan() -> None:
    shooting_unit = _Unit(
        "unit:shooter",
        movement=6,
        wargear=[
            _Wargear(
                "ranged",
                _Profile(range_inches=30, attacks=5, skill=3, strength=5, ap=-1, damage=2),
            )
        ],
    )
    target = _Unit("target:shoot", wounds=8, position=(15.0, 0.0, 0.0))
    game, player, _opponent = _build_custom_game([shooting_unit], [target])

    plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    unit_task = plan["unit_tasks"]["unit:shooter"]
    movement_task = plan["movement_plan"]["unit_positioning_tasks"]["unit:shooter"]
    fire_assignment = plan["shooting_plan"]["unit_fire_assignments"]["unit:shooter"]
    charge_assignment = plan["charge_plan"]["unit_charge_assignments"]["unit:shooter"]

    assert unit_task["role"] == "shooting_first"
    assert unit_task["primary_target_unit_id"] == "target:shoot"
    assert unit_task["shooting_intent"] == "planned_focus_fire"
    assert movement_task["avoid_becoming_shooting_ineligible"] is True
    assert movement_task["required_los_to_unit_ids"] == ["target:shoot"]
    assert fire_assignment["primary_target_unit_id"] == "target:shoot"
    assert fire_assignment["expected_damage_by_target"]["target:shoot"] > 0.0
    assert fire_assignment["requires_los"] is True
    assert charge_assignment["intentionally_skip_shooting"] is False


def test_commander_context_attaches_to_unit_scoped_decision() -> None:
    game, player, unit = _build_game()
    request = _yes_no_request(player.id, unit.id)

    game.request_decision(request)

    assert request.context["general_plan_id"] == game.get_or_create_general_plan(player.id).plan_id
    assert "general_plan" not in request.context
    assert request.context["battle_round_plan_id"].endswith(":battle_round")
    assert "battle_round_plan" not in request.context
    assert request.context["unit_battle_task"]["unit_id"] == unit.id
    assert request.context["commander_movement_task"]["unit_id"] == unit.id
    assert request.context["commander_fire_assignment"]["unit_id"] == unit.id
    assert request.context["commander_charge_assignment"]["unit_id"] == unit.id
    assert request.context["commander_fight_assignment"]["unit_id"] == unit.id


def test_disembark_decision_context_receives_commander_disembark_slice() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_custom_game([transport, passenger], [])
    request = DecisionRequest.create(
        DECISION_DISEMBARK,
        "Disembark?",
        player_id=player.id,
        options=[
            DecisionOption.create("Remain embarked", payload={"unit_id": passenger.id, "skip": True}),
            DecisionOption.create(
                "Disembark",
                payload={"unit_id": passenger.id, "transport_id": transport.id},
            ),
        ],
        context={"unit_id": passenger.id, "transport_id": transport.id},
    )

    game.request_decision(request)

    assert request.context["commander_transport_assignment"]["unit_id"] == passenger.id
    assert request.context["commander_disembark_assignment"]["intent"] == "stay_embarked"
    assert "commander_embark_assignment" not in request.context
    assert "battle_round_plan" not in request.context
    assert "general_plan" not in request.context


def test_embark_decision_context_receives_commander_embark_slice() -> None:
    rider = _Unit("unit:rider", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    game, player, _opponent = _build_custom_game([transport, rider], [])
    request = DecisionRequest.create(
        DECISION_EMBARK,
        "Embark?",
        player_id=player.id,
        options=[
            DecisionOption.create("Do not embark", payload={"unit_id": rider.id, "skip": True}),
            DecisionOption.create(
                "Embark",
                payload={"unit_id": rider.id, "transport_id": transport.id},
            ),
        ],
        context={"unit_id": rider.id, "transport_ids": [transport.id]},
    )

    game.request_decision(request)

    assert request.context["commander_transport_assignment"]["unit_id"] == rider.id
    assert request.context["commander_embark_assignment"]["intent"] == "embark_after_action"
    assert request.context["commander_embark_assignment"]["transport_unit_id"] == transport.id
    assert "commander_disembark_assignment" not in request.context


def test_transport_unit_context_receives_delivery_assignment() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_custom_game([transport, passenger], [])
    request = _yes_no_request(player.id, transport.id)

    game.request_decision(request)

    assert request.context["commander_transport_assignment"]["unit_id"] == transport.id
    assert request.context["commander_transport_assignment"]["intent"] == "deliver_to_staging_region"


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
            "general_plan": {"plan_id": "caller-provided-general"},
        },
    )

    game.request_decision(request)

    assert request.context["battle_round_plan_id"].endswith(":battle_round")
    assert "battle_round_plan" not in request.context
    assert request.context["general_plan_id"] == game.get_or_create_general_plan(player.id).plan_id
    assert "general_plan" not in request.context


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


def test_full_general_plan_attaches_when_request_enables_audit_payload() -> None:
    game, player, unit = _build_game()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={"unit_id": unit.id, "include_full_general_plan": True},
    )

    game.request_decision(request)

    assert request.context["general_plan"]["plan_id"] == request.context["general_plan_id"]
    assert "battle_round_plan" not in request.context


def test_full_battle_round_plan_attaches_when_game_enables_audit_payload() -> None:
    game, player, unit = _build_game()
    game.attach_full_battle_round_plan_context = True
    request = _yes_no_request(player.id, unit.id)

    game.request_decision(request)

    assert (
        request.context["battle_round_plan"]["plan_id"]
        == request.context["battle_round_plan_id"]
    )


def test_full_general_plan_attaches_when_game_enables_audit_payload() -> None:
    game, player, unit = _build_game()
    game.attach_full_general_plan_context = True
    request = _yes_no_request(player.id, unit.id)

    game.request_decision(request)

    assert request.context["general_plan"]["plan_id"] == request.context["general_plan_id"]
    assert "battle_round_plan" not in request.context


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


def test_shooting_phase_start_repairs_movement_variance_for_shooting_only() -> None:
    game, player, unit = _build_game()
    before_count = game.get_or_create_battle_round_plan(player.id).invalidation.repair_count

    game.event_system.publish("unit_move_ended", unit=unit, action="normal_move")
    game.event_system.publish(
        "phase_start",
        player=player,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
    )

    flags = game.get_commander_dirty_flags(player.id)
    repaired_plan = game.get_or_create_battle_round_plan(player.id)

    assert repaired_plan.invalidation.repair_count == before_count + 1
    assert flags.shooting_plan_dirty is False
    assert flags.charge_plan_dirty is True
    assert flags.recommended_replan_scope() == "charge_only"


def test_charge_and_fight_phase_repairs_consume_failed_charge_variance() -> None:
    game, player, unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)

    game.event_system.publish("charge_move_failed", unit=unit)
    game.event_system.publish(
        "phase_start",
        player=player,
        phase=SimpleNamespace(name="CHARGE_PHASE"),
    )
    after_charge = game.get_or_create_battle_round_plan(player.id)
    charge_flags = game.get_commander_dirty_flags(player.id)

    assert after_charge.invalidation.repair_count == 1
    assert charge_flags.charge_plan_dirty is False
    assert charge_flags.fight_plan_dirty is True
    assert charge_flags.status() == "major_variance"

    game.event_system.publish(
        "phase_start",
        player=player,
        phase=SimpleNamespace(name="FIGHT_PHASE"),
    )
    after_fight = game.get_or_create_battle_round_plan(player.id)
    fight_flags = game.get_commander_dirty_flags(player.id)

    assert after_fight.invalidation.repair_count == 2
    assert fight_flags.any_dirty() is False


def test_destroyed_target_phase_repair_removes_dead_target_assignments() -> None:
    game, player, _unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)
    target = game.players[1].army.units[1]
    target.alive = False

    game.event_system.publish("unit_destroyed", unit=target)
    game.event_system.publish(
        "phase_start",
        player=player,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
    )

    repaired = game.get_or_create_battle_round_plan(player.id).to_dict()
    primary_targets = {
        str(task.get("primary_target_unit_id", ""))
        for task in repaired["unit_tasks"].values()
        if str(task.get("primary_target_unit_id", ""))
    }

    assert "target:big" not in [target["target_unit_id"] for target in repaired["priority_targets"]]
    assert "target:big" not in repaired["shooting_plan"]["target_fire_plans"]
    assert "target:big" not in primary_targets
    assert game.get_commander_dirty_flags(player.id).any_dirty() is False


def test_commander_phase_start_repair_is_idempotent_for_consumed_scope() -> None:
    game, player, unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)

    game.event_system.publish("unit_move_ended", unit=unit, action="normal_move")
    phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.event_system.publish("phase_start", player=player, phase=phase)
    first_count = game.get_or_create_battle_round_plan(player.id).invalidation.repair_count

    game.event_system.publish("phase_start", player=player, phase=phase)
    second_count = game.get_or_create_battle_round_plan(player.id).invalidation.repair_count

    assert first_count == 1
    assert second_count == first_count


def test_phase_report_records_repair_scope_and_pre_post_dirty_flags() -> None:
    game, player, unit = _build_game()
    game.get_or_create_battle_round_plan(player.id)

    game.event_system.publish("unit_move_ended", unit=unit, action="normal_move")
    phase = SimpleNamespace(name="SHOOTING_PHASE")
    game.event_system.publish("phase_start", player=player, phase=phase)
    game.event_system.publish("phase_end", player=player, phase=phase)
    report = game.get_commander_phase_reports(player.id)[-1].to_dict()
    repair = report["metadata"]["repair"]

    assert repair["scope"] == "shooting_only"
    assert repair["pre_dirty_flags"]["shooting_plan_dirty"] is True
    assert repair["post_dirty_flags"]["shooting_plan_dirty"] is False
    assert report["metadata"]["dirty_flags"]["charge_plan_dirty"] is True
