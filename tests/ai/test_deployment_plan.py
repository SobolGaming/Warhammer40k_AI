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
        scout_distance: float | None = None,
        infiltrate: bool = False,
        deployed: bool = True,
        reserve_status: str = "deployed",
    ) -> None:
        self._id = unit_id
        self.id = unit_id
        self.name = unit_id
        self.deployed = bool(deployed)
        self.reserve_status = str(reserve_status)
        self.keywords = list(keywords or [])
        self._scout_distance = scout_distance
        self._infiltrate = bool(infiltrate)
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

    def has_scout(self) -> tuple[bool, float]:
        if self._scout_distance is not None:
            return bool(self._scout_distance > 0.0), float(self._scout_distance)
        if any(str(keyword).upper().startswith("SCOUT") for keyword in self.keywords):
            return True, 6.0
        return False, 0.0

    def has_infiltrate(self) -> bool:
        return bool(
            self._infiltrate
            or any(str(keyword).upper().startswith("INFILTRATOR") for keyword in self.keywords)
        )

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
    guardrails = data["metadata"]["performance_guardrails"]
    assert guardrails["plan_build_budget_ms"] > 0
    assert guardrails["repair_budget_ms"] > 0
    assert guardrails["context_payload_warning_bytes"] > 0
    assert guardrails["unit_task_count"] == 1


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


def test_scout_unit_gets_early_deployment_tempo_metadata() -> None:
    scout = _Unit("unit:scouts", scout_distance=6.0, deployed=False)
    game, player, _opponent = _build_game([scout], [])

    plan = game.get_or_create_deployment_plan(player.id).to_dict()
    task = plan["unit_tasks"]["unit:scouts"]
    capability = plan["tempo_capabilities"]["unit:scouts"]
    projection = plan["scout_projections"]["unit:scouts"]
    state = plan["information_state"]

    assert capability["has_scout"] is True
    assert capability["early_drop_priority"] > 0.0
    assert task["preferred_drop_window"] == "early"
    assert task["deployment_sequence_priority"] > 0.0
    assert task["has_scout"] is True
    assert task["scout_lane_targets"]
    assert task["no_mans_land_pressure_regions"]
    assert state["own_scout_unit_ids_unplaced"] == ["unit:scouts"]
    assert projection["can_reach_cover"] is True
    assert projection["can_screen_lane_ids"]


def test_infiltrate_unit_gets_early_deployment_tempo_metadata() -> None:
    infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    game, player, _opponent = _build_game([infiltrator], [])

    plan = game.get_or_create_deployment_plan(player.id).to_dict()
    task = plan["unit_tasks"]["unit:infiltrator"]
    capability = plan["tempo_capabilities"]["unit:infiltrator"]
    projection = plan["infiltrate_projections"]["unit:infiltrator"]
    state = plan["information_state"]

    assert capability["has_infiltrate"] is True
    assert capability["early_drop_priority"] > 0.0
    assert task["preferred_drop_window"] == "early"
    assert task["has_infiltrate"] is True
    assert task["counter_scout_regions"]
    assert task["infiltrate_screen_regions"]
    assert state["own_infiltrate_unit_ids_unplaced"] == ["unit:infiltrator"]
    assert projection["blocks_enemy_scout_lane_ids"]
    assert projection["denies_enemy_forward_regions"]


def test_enemy_scout_pressure_increases_own_infiltrate_counter_scout_priority() -> None:
    base_infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    game_without_scout, player_a, _opponent_a = _build_game([base_infiltrator], [_Unit("enemy:line")])
    base_priority = (
        game_without_scout
        .get_or_create_deployment_plan(player_a.id)
        .to_dict()["unit_tasks"]["unit:infiltrator"]["deployment_sequence_priority"]
    )

    pressured_infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    enemy_scout = _Unit("enemy:scout", scout_distance=6.0)
    game_with_scout, player_b, _opponent_b = _build_game([pressured_infiltrator], [enemy_scout])
    pressured_plan = game_with_scout.get_or_create_deployment_plan(player_b.id).to_dict()
    pressured_priority = pressured_plan["unit_tasks"]["unit:infiltrator"]["deployment_sequence_priority"]

    assert pressured_priority > base_priority
    assert pressured_plan["information_state"]["enemy_scout_unit_ids_known"] == ["enemy:scout"]


def test_enemy_infiltrate_pressure_marks_scout_lanes_blocked() -> None:
    base_scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    game_without_blocker, player_a, _opponent_a = _build_game([base_scout], [_Unit("enemy:line")])
    base_capability = game_without_blocker.get_or_create_deployment_plan(player_a.id).to_dict()[
        "tempo_capabilities"
    ]["unit:scout"]

    pressured_scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    enemy_infiltrator = _Unit("enemy:infiltrator", infiltrate=True)
    game_with_blocker, player_b, _opponent_b = _build_game([pressured_scout], [enemy_infiltrator])
    pressured_plan = game_with_blocker.get_or_create_deployment_plan(player_b.id).to_dict()
    pressured_capability = pressured_plan["tempo_capabilities"]["unit:scout"]
    scout_lanes = pressured_plan["information_state"]["scout_lanes"]

    assert pressured_capability["early_drop_priority"] < base_capability["early_drop_priority"]
    assert pressured_capability["metadata"]["enemy_infiltrate_pressure"] is True
    assert all(lane["blocked_by_enemy_infiltrate"] is True for lane in scout_lanes.values())
    assert pressured_plan["information_state"]["enemy_infiltrate_unit_ids_known"] == ["enemy:infiltrator"]


def test_first_turn_unknown_marks_fragile_forward_tempo_exposure_risk() -> None:
    scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    game, player, _opponent = _build_game([scout, infiltrator], [])

    plan = game.get_or_create_deployment_plan(player.id).to_dict()

    assert plan["first_turn_unknown"] is True
    assert plan["tempo_capabilities"]["unit:scout"]["reveal_risk"] > 0.0
    assert plan["tempo_capabilities"]["unit:infiltrator"]["reveal_risk"] > 0.0
    assert plan["unit_tasks"]["unit:scout"]["avoid_alpha_exposure"] is True
    assert plan["unit_tasks"]["unit:infiltrator"]["avoid_alpha_exposure"] is True


def test_deployment_context_attaches_tempo_and_projection_slices() -> None:
    scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    game, player, _opponent = _build_game([scout, infiltrator], [])

    scout_request = _deployment_move_request(player.id, scout.id)
    infiltrate_request = _deployment_move_request(player.id, infiltrator.id)
    game.request_decision(scout_request)
    game.request_decision(infiltrate_request)

    assert scout_request.context["deployment_tempo_capability"]["has_scout"] is True
    assert scout_request.context["scout_projection"]["unit_id"] == scout.id
    assert "deployment_plan" not in scout_request.context
    assert infiltrate_request.context["deployment_tempo_capability"]["has_infiltrate"] is True
    assert infiltrate_request.context["infiltrate_projection"]["unit_id"] == infiltrator.id
    assert "deployment_plan" not in infiltrate_request.context


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
    assert game.get_orchestration_audit_counters()["deployment_plan_dirty_marked"] == 1


def test_enemy_scout_deployment_event_records_tempo_variance() -> None:
    own_unit = _Unit("unit:own", deployed=False)
    enemy_scout = _Unit("enemy:scout", scout_distance=6.0, deployed=True)
    game, player, opponent = _build_game([own_unit], [enemy_scout])
    game.get_or_create_deployment_plan(player.id)

    game.event_system.publish("unit_deployed", unit=enemy_scout, player=opponent)
    flags = game.get_deployment_dirty_flags(player.id)

    assert flags.remaining_drops_dirty is True
    assert flags.enemy_information_dirty is True
    assert "enemy_scout_deployed:enemy:scout" in flags.reasons
    assert flags.max_severity >= 0.6


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
    assert game.get_orchestration_audit_counters()["deployment_plan_repaired"] == 1
    repair_event = game.get_orchestration_audit_events(event_kind="deployment_plan_repaired")[-1]
    assert repair_event["metadata"]["scope"] == "remaining_drops"


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
