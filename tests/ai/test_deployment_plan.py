from __future__ import annotations

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CONFIRM_YES_NO,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.roster.player import Player


class _Profile:
    def __init__(
        self,
        *,
        attacks: int = 1,
        strength: int = 4,
        ap: int = 0,
        damage: int = 1,
    ) -> None:
        self.attacks = attacks
        self.strength = strength
        self.ap = ap
        self.damage = damage


class _Wargear:
    _next_id = 0

    def __init__(self, mode: str, profile: _Profile) -> None:
        type(self)._next_id += 1
        self._id = f"wargear:{mode}:{type(self)._next_id}"
        self.id = self._id
        self.type = mode
        self.profiles = {"default": profile}

    def is_ranged(self) -> bool:
        return self.type == "ranged"

    def is_melee(self) -> bool:
        return self.type == "melee"


class _Model:
    def __init__(
        self,
        model_id: str,
        *,
        wounds: int = 1,
        objective_control: int = 1,
        wargear: list[_Wargear] | None = None,
    ) -> None:
        self._id = model_id
        self.wounds = wounds
        self.objective_control = objective_control
        self.wargear = list(wargear or [])
        self.keywords = []
        self.faction_keywords = []


class _Unit:
    def __init__(
        self,
        unit_id: str,
        *,
        wounds: int = 1,
        objective_control: int = 1,
        wargear: list[_Wargear] | None = None,
        keywords: list[str] | None = None,
        deployed: bool = True,
        reserve_status: str = "deployed",
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.deployed = bool(deployed)
        self.reserve_status = str(reserve_status)
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.is_transport = "TRANSPORT" in {str(keyword).upper() for keyword in self.keywords}
        self.transport_capacity = 10 if self.is_transport else 0
        self.transport_passengers = []
        self.embarked_in = None
        self.models = [
            _Model(
                f"{unit_id}:model",
                wounds=wounds,
                objective_control=objective_control,
                wargear=wargear,
            )
        ]
        self.parent_army = None

    def get_parent_army(self):
        return self.parent_army

    def get_attached_unit_root(self):
        return self

    def is_in_reserves(self) -> bool:
        return self.reserve_status in {"reserves", "strategic_reserves"}

    def is_embarked(self) -> bool:
        return self.embarked_in is not None or self.reserve_status == "embarked"

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


def _build_game(friendly_units: list[_Unit], enemy_units: list[_Unit]) -> tuple[Game, Player, Player]:
    player = Player("P1")
    opponent = Player("P2")
    player.army = _Army("army:p1", friendly_units)
    opponent.army = _Army("army:p2", enemy_units)
    player.army.set_player(player)
    opponent.army.set_player(opponent)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[player, opponent])
    game.selected_mission_info = {
        "mission_id": "mission:take_and_hold",
        "deployment_definition_id": "deployment:dawn_of_war",
        "layout": 2,
        "secondary_mission_mode": "tactical",
    }
    return game, player, opponent


def _deployment_move_request(player_id: str, unit_id: str) -> DecisionRequest:
    return DecisionRequest.create(
        DECISION_MOVE_UNIT,
        "Deploy",
        player_id=player_id,
        options=[
            DecisionOption.create(
                "Place",
                payload={
                    "unit_id": unit_id,
                    "action": "place",
                    "model_positions": [
                        {
                            "model_id": f"{unit_id}:model",
                            "position": [6.0, 6.0, 0.0],
                        }
                    ],
                },
            )
        ],
        context={"unit_id": unit_id, "placement_kind": "deployment"},
    )


def test_deployment_plan_is_cached_and_serializable() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[
            _Wargear("ranged", _Profile(attacks=6, strength=8, ap=-2, damage=3)),
        ],
    )
    enemy = _Unit("enemy:unplaced", deployed=False)
    game, player, _opponent = _build_game([shooter], [enemy])

    first = game.get_or_create_deployment_plan(player.id)
    second = game.get_or_create_deployment_plan(player.id)
    data = first.to_dict()

    assert first is second
    assert data["plan_id"] == f"deployment:{player.id}:setup"
    assert data["mission_id"] == "mission:take_and_hold"
    assert data["deployment_map_id"] == "deployment:dawn_of_war"
    assert data["terrain_layout_id"] == "2"
    assert data["first_turn_unknown"] is True
    assert data["secondary_mode"] == "tactical"
    assert data["information_state"]["enemy_unplaced_unit_ids"] == ["enemy:unplaced"]
    assert data["metadata"]["general_plan_id"] == game.get_or_create_general_plan(player.id).plan_id


def test_deployment_context_is_slim_and_attaches_unit_task() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[
            _Wargear("ranged", _Profile(attacks=6, strength=8, ap=-2, damage=3)),
        ],
    )
    game, player, _opponent = _build_game([shooter], [])
    request = _deployment_move_request(player.id, shooter.id)

    game.request_decision(request)

    assert request.context["deployment_plan_id"] == game.get_or_create_deployment_plan(player.id).plan_id
    assert "deployment_plan" not in request.context
    assert request.context["unit_deployment_task"]["unit_id"] == shooter.id
    assert request.context["unit_deployment_task"]["role"] == "hide"
    assert request.context["unit_deployment_task"]["needs_obscuring"] is True
    assert request.context["deployment_dirty_flags"]["status"] == "on_plan"
    assert request.context["deployment_replan_scope"] == "none"


def test_full_deployment_plan_attaches_only_with_audit_opt_in() -> None:
    unit = _Unit("unit:line")
    game, player, _opponent = _build_game([unit], [])
    request = _deployment_move_request(player.id, unit.id)
    request.context["include_full_deployment_plan"] = True

    game.request_decision(request)

    assert request.context["deployment_plan"]["plan_id"] == request.context["deployment_plan_id"]
    assert "battle_round_plan" not in request.context
    assert "general_plan" not in request.context


def test_preexisting_full_deployment_plan_is_stripped_without_audit_opt_in() -> None:
    unit = _Unit("unit:line")
    game, player, _opponent = _build_game([unit], [])
    request = _deployment_move_request(player.id, unit.id)
    request.context["deployment_plan"] = {"plan_id": "caller-provided"}

    game.request_decision(request)

    assert request.context["deployment_plan_id"] == game.get_or_create_deployment_plan(player.id).plan_id
    assert "deployment_plan" not in request.context


def test_high_value_shooter_gets_hide_posture_when_first_turn_unknown() -> None:
    shooter = _Unit(
        "unit:las",
        wargear=[
            _Wargear("ranged", _Profile(attacks=4, strength=12, ap=-4, damage=6)),
        ],
    )
    game, player, _opponent = _build_game([shooter], [])

    task = game.get_or_create_deployment_plan(player.id).to_dict()["unit_tasks"]["unit:las"]

    assert task["role"] == "hide"
    assert task["avoid_alpha_exposure"] is True
    assert "obscuring_home" in task["preferred_regions"]
    assert "alpha_exposed_lane" in task["forbidden_regions"]


def test_screen_unit_gets_forward_screen_role() -> None:
    screen = _Unit("unit:scouts", keywords=["SCOUTS"])
    game, player, _opponent = _build_game([screen], [])

    task = game.get_or_create_deployment_plan(player.id).to_dict()["unit_tasks"]["unit:scouts"]

    assert task["role"] == "screen"
    assert "forward_screen" in task["preferred_regions"]
    assert task["tactical_flexibility"] > 0.0


def test_transport_deployment_task_links_passenger_doctrine() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_game([transport, passenger], [])

    plan = game.get_or_create_deployment_plan(player.id).to_dict()
    transport_task = plan["transport_tasks"]["unit:transport"]
    passenger_task = plan["unit_tasks"]["unit:passenger"]

    assert transport_task["passenger_unit_ids"] == ["unit:passenger"]
    assert transport_task["initial_deployment_role"] == "deliver"
    assert transport_task["delivery_round"] == 2
    assert transport_task["preserve_passengers"] is True
    assert passenger_task["role"] == "transported"
    assert passenger_task["supports_transport_plan"] is True


def test_embarked_and_enemy_reserve_state_appears_in_information_state() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"], reserve_status="embarked")
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    transport.transport_passengers = [passenger]
    enemy_reserve = _Unit("enemy:reserve", deployed=False, reserve_status="strategic_reserves")
    game, player, _opponent = _build_game([transport, passenger], [enemy_reserve])

    state = game.get_or_create_deployment_plan(player.id).to_dict()["information_state"]

    assert state["own_embarked_unit_ids"] == ["unit:passenger"]
    assert state["enemy_reserve_unit_ids"] == ["enemy:reserve"]


def test_deployment_context_attaches_transport_task_for_passenger() -> None:
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    game, player, _opponent = _build_game([transport, passenger], [])
    request = _deployment_move_request(player.id, passenger.id)

    game.request_decision(request)

    assert request.context["unit_deployment_task"]["role"] == "transported"
    assert request.context["transport_deployment_task"]["transport_unit_id"] == transport.id
    assert request.context["transport_deployment_task"]["passenger_unit_ids"] == [passenger.id]


def test_enemy_deployment_event_dirties_remaining_own_drops() -> None:
    own_unit = _Unit("unit:own", deployed=False)
    enemy_unit = _Unit("enemy:drop", deployed=True)
    game, player, opponent = _build_game([own_unit], [enemy_unit])
    game.get_or_create_deployment_plan(player.id)

    game.event_system.publish("deployment_unit_deployed", unit=enemy_unit, player=opponent)
    flags = game.get_deployment_dirty_flags(player.id)

    assert flags.remaining_drops_dirty is True
    assert flags.enemy_information_dirty is True
    assert flags.recommended_replan_scope() == "remaining_drops"


def test_repair_deployment_plan_consumes_dirty_flags() -> None:
    own_unit = _Unit("unit:own", deployed=False)
    enemy_unit = _Unit("enemy:drop", deployed=True)
    game, player, opponent = _build_game([own_unit], [enemy_unit])
    before = game.get_or_create_deployment_plan(player.id)
    game.event_system.publish("unit_deployed", unit=enemy_unit, player=opponent)

    report = game.repair_deployment_plan(
        player.id,
        scope="remaining_drops",
        phase_name="DEPLOYMENT",
    )
    after = game.get_or_create_deployment_plan(player.id)

    assert report["repaired"] is True
    assert report["scope"] == "remaining_drops"
    assert after.repair_count == before.repair_count + 1
    assert game.get_deployment_dirty_flags(player.id).any_dirty() is False


def test_non_deployment_decision_does_not_attach_deployment_plan() -> None:
    unit = _Unit("unit:line")
    game, player, _opponent = _build_game([unit], [])
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[
            DecisionOption.create("Yes", payload={"choice": True}),
            DecisionOption.create("No", payload={"choice": False}),
        ],
        context={"unit_id": unit.id, "deployment_plan": {"plan_id": "caller-provided"}},
    )

    game.request_decision(request)

    assert "deployment_plan_id" not in request.context
    assert "unit_deployment_task" not in request.context
    assert "deployment_plan" not in request.context
