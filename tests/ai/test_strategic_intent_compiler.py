from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from warhammer40k_ai.engine.battlefield import Battlefield, BattlefieldSize
from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_SCOUT_MOVE
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest
from warhammer40k_ai.engine.game import Game
from warhammer40k_ai.engine.general_plan import GeneralRoundDirective, LimitedResourcePolicy
from warhammer40k_ai.engine.strategic_intent_compiler import (
    compile_general_intent_to_commander_orders,
    compile_round_commander_directive,
)
from warhammer40k_ai.roster.player import Player


class _Profile:
    def __init__(
        self,
        *,
        attacks: int = 1,
        strength: int = 4,
        ap: int = 0,
        damage: int = 1,
        range_inches: int = 24,
    ) -> None:
        self.attacks = attacks
        self.strength = strength
        self.ap = ap
        self.damage = damage
        self.range = SimpleNamespace(max=range_inches)


class _Wargear:
    _next_id = 0

    def __init__(self, mode: str, profile: _Profile, name: str = "") -> None:
        type(self)._next_id += 1
        self.id = f"wargear:{mode}:{type(self)._next_id}"
        self.name = name or self.id
        self.type = mode
        self.profiles = {"default": profile}

    def is_ranged(self) -> bool:
        return self.type == "ranged"

    def is_melee(self) -> bool:
        return self.type == "melee"


class _Model:
    def __init__(self, model_id: str, *, wounds: int = 1, oc: int = 1, wargear: list[_Wargear] | None = None) -> None:
        self.id = model_id
        self._id = model_id
        self.wounds = wounds
        self.objective_control = oc
        self.wargear = list(wargear or [])
        self.keywords = []
        self.faction_keywords = []


class _Unit:
    def __init__(
        self,
        unit_id: str,
        *,
        keywords: list[str] | None = None,
        wargear: list[_Wargear] | None = None,
        wounds: int = 1,
        oc: int = 1,
        scout_distance: float = 0.0,
        infiltrate: bool = False,
        deployed: bool = True,
    ) -> None:
        self.id = unit_id
        self._id = unit_id
        self.name = unit_id
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.models = [_Model(f"{unit_id}:model", wounds=wounds, oc=oc, wargear=wargear)]
        self.scout_distance = scout_distance
        self.infiltrate = infiltrate
        self.deployed = deployed
        self.reserve_status = "deployed" if deployed else "undeployed"
        self.embarked_in = None
        self.transport_passengers = []

    def can_transport(self, other: object) -> bool:
        return "TRANSPORT" in self.keywords and other is not self


class _Army:
    def __init__(self, army_id: str, units: list[_Unit]) -> None:
        self.id = army_id
        self.units = list(units)
        self.player = None

    def set_player(self, player: Player) -> None:
        self.player = player


def _build_game(friendly: list[_Unit], enemy: list[_Unit]) -> tuple[Game, Player, Player]:
    player = Player("P1")
    opponent = Player("P2")
    player.army = _Army("army:p1", friendly)
    opponent.army = _Army("army:p2", enemy)
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


def _install_general_plan(game: Game, player: Player, general_plan: object) -> None:
    game._general_plans = {player.id: general_plan}
    game._deployment_order_bundles = {}
    game._prebattle_order_bundles = {}
    game._deployment_plans = {}
    game._battle_round_plans = {}


def test_stage_push_and_preserve_directives_compile_expected_budgets() -> None:
    game, player, _opponent = _build_game([_Unit("unit:line")], [])
    general = game.get_or_create_general_plan(player.id)

    stage = compile_round_commander_directive(general, player_id=player.id, battle_round=1)
    push = compile_round_commander_directive(general, player_id=player.id, battle_round=2)
    preserve = compile_round_commander_directive(general, player_id=player.id, battle_round=5)

    assert stage.aggression_budget < 0.5
    assert stage.resource_budget < 0.5
    assert stage.primary_phase_focus == "movement"
    assert push.aggression_budget >= 0.75
    assert push.resource_budget >= 0.7
    assert preserve.exposure_budget < stage.exposure_budget
    assert preserve.primary_phase_focus == "score"


def test_deployment_order_bundle_handles_uncertainty_scout_infiltrate_and_transport() -> None:
    scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    passenger = _Unit("unit:passenger", keywords=["INFANTRY"])
    transport = _Unit("unit:transport", keywords=["TRANSPORT"])
    passenger.embarked_in = transport
    passenger.reserve_status = "embarked"
    transport.transport_passengers = [passenger]
    enemy_scout = _Unit("enemy:scout", scout_distance=6.0)
    enemy_infiltrator = _Unit("enemy:infiltrator", infiltrate=True)
    game, player, _opponent = _build_game([scout, infiltrator, transport, passenger], [enemy_scout, enemy_infiltrator])

    deployment_orders = game.get_or_create_deployment_order_bundle(player.id)
    data = deployment_orders.to_dict()

    assert data["doctrine"]["first_turn_unknown"] is True
    assert data["doctrine"]["alpha_exposure_risk_weight"] > 1.0
    assert data["information_state"]["enemy_scout_unit_ids_known"] == ["enemy:scout"]
    assert data["information_state"]["enemy_infiltrate_unit_ids_known"] == ["enemy:infiltrator"]
    assert data["information_state"]["blocked_scout_lane_ids"]
    assert data["tempo_orders"]["unit:scout"]["has_scout"] is True
    assert data["tempo_orders"]["unit:scout"]["early_drop_priority"] > 0.0
    assert data["unit_orders"]["unit:scout"]["preferred_drop_window"] == "early"
    assert data["tempo_orders"]["unit:infiltrator"]["has_infiltrate"] is True
    assert data["tempo_orders"]["unit:infiltrator"]["counter_scout_region_ids"]
    assert data["transport_orders"]["unit:transport"]["passenger_unit_ids"] == ["unit:passenger"]


def test_prebattle_orders_compile_scout_and_infiltrate_slices() -> None:
    scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    infiltrator = _Unit("unit:infiltrator", infiltrate=True, deployed=False)
    enemy_scout = _Unit("enemy:scout", scout_distance=6.0)
    game, player, _opponent = _build_game([scout, infiltrator], [enemy_scout])

    prebattle = game.get_or_create_prebattle_order_bundle(player.id).to_dict()

    scout_order = prebattle["scout_orders"]["unit:scout"]
    infiltrate_order = prebattle["infiltrate_orders"]["unit:infiltrator"]
    assert scout_order["intent"] in {"move_to_cover", "threaten_objective", "screen_lane"}
    assert scout_order["destination_region_ids"] or scout_order["cover_region_ids"]
    assert infiltrate_order["intent"] in {"counter_scout", "forward_screen", "objective_screen"}
    assert infiltrate_order["blocks_enemy_scout_lane_ids"]
    assert prebattle["metadata"]["transport_order_count"] == 0


def test_commander_orders_compile_targets_preserve_and_resource_authorization() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[_Wargear("ranged", _Profile(attacks=2, strength=12, ap=-3, damage=6), name="hunter-killer missile")],
    )
    home = _Unit("unit:home")
    high_target = _Unit("target:high", wounds=12, oc=5)
    low_target = _Unit("target:low", wounds=2, oc=1)
    game, player, _opponent = _build_game([shooter, home], [high_target, low_target])
    general = game.get_or_create_general_plan(player.id)
    directive = GeneralRoundDirective(
        battle_round=2,
        posture="push",
        push_priority=0.9,
        cp_reserve_target=1.0,
        preserve_unit_ids=["unit:home"],
    )
    policies = dict(general.limited_resource_policy)
    policies["unit:shooter:one_shot_weapon"] = LimitedResourcePolicy(
        resource_id="unit:shooter:one_shot_weapon",
        resource_kind="one_shot_weapon",
        status="reserved",
        reserved_for_round=2,
        authorization_threshold=0.8,
        owner_unit_id="unit:shooter",
    )
    custom_general = replace(
        general,
        battle_round_directives={2: directive},
        limited_resource_policy=policies,
    )
    deployment_orders = game.get_or_create_deployment_order_bundle(player.id)
    prebattle_orders = game.get_or_create_prebattle_order_bundle(player.id)
    tier1 = game.get_or_create_tier1_plan(player.id)
    tier2 = game.get_or_create_tier2_task_bundle(player.id)
    analysis = game.get_or_create_battle_round_plan(player.id).metadata["analysis_snapshot"]

    commander_orders = compile_general_intent_to_commander_orders(
        game,
        custom_general,
        deployment_orders,
        prebattle_orders,
        tier1,
        tier2,
        analysis,
        battle_round=2,
        player_id=player.id,
    ).to_dict()

    assert commander_orders["directive"]["posture"] == "push"
    assert commander_orders["target_orders"]["target:high"]["intent"] == "kill"
    assert commander_orders["target_orders"]["target:high"]["desired_kill_probability"] >= 0.75
    assert commander_orders["unit_orders"]["unit:home"]["role"] == "preserve"
    assert commander_orders["unit_orders"]["unit:home"]["preserve"] is True
    authorization = commander_orders["resource_authorizations"]["unit:shooter:one_shot_weapon"]
    assert authorization["status"] == "conditionally_authorized"
    assert "target:high" in authorization["allowed_target_unit_ids"]


def test_commander_resource_authorization_stays_reserved_before_reserved_round() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[_Wargear("ranged", _Profile(attacks=2, strength=12, ap=-3, damage=6), name="hunter-killer missile")],
    )
    high_target = _Unit("target:high", wounds=12, oc=5)
    game, player, _opponent = _build_game([shooter], [high_target])
    general = game.get_or_create_general_plan(player.id)
    directive = GeneralRoundDirective(
        battle_round=1,
        posture="stage",
        push_priority=0.2,
        cp_reserve_target=1.0,
    )
    policies = dict(general.limited_resource_policy)
    policies["unit:shooter:one_shot_weapon"] = LimitedResourcePolicy(
        resource_id="unit:shooter:one_shot_weapon",
        resource_kind="one_shot_weapon",
        status="reserved",
        reserved_for_round=2,
        authorization_threshold=0.8,
        owner_unit_id="unit:shooter",
    )
    custom_general = replace(
        general,
        battle_round_directives={1: directive},
        limited_resource_policy=policies,
    )
    deployment_orders = game.get_or_create_deployment_order_bundle(player.id)
    prebattle_orders = game.get_or_create_prebattle_order_bundle(player.id)
    tier1 = game.get_or_create_tier1_plan(player.id)
    tier2 = game.get_or_create_tier2_task_bundle(player.id)
    analysis = game.get_or_create_battle_round_plan(player.id).metadata["analysis_snapshot"]

    commander_orders = compile_general_intent_to_commander_orders(
        game,
        custom_general,
        deployment_orders,
        prebattle_orders,
        tier1,
        tier2,
        analysis,
        battle_round=1,
        player_id=player.id,
    ).to_dict()

    authorization = commander_orders["resource_authorizations"]["unit:shooter:one_shot_weapon"]
    assert authorization["status"] == "reserved"
    assert authorization["allowed_target_unit_ids"] == []


def test_stage_round_downshifts_constrained_future_charge_order_until_push_round() -> None:
    melee = _Unit(
        "unit:melee",
        keywords=["INFANTRY"],
        wargear=[_Wargear("melee", _Profile(attacks=6, strength=8, ap=-2, damage=2), name="chainaxe")],
    )
    target = _Unit("target:high", wounds=10, oc=4)
    game, player, _opponent = _build_game([melee], [target])
    general = game.get_or_create_general_plan(player.id)
    custom_general = replace(
        general,
        battle_round_directives={
            1: GeneralRoundDirective(battle_round=1, posture="stage", push_priority=0.2),
            2: GeneralRoundDirective(battle_round=2, posture="push", push_priority=0.9),
        },
        target_priority_doctrine={
            "unit_order_overrides": {
                "unit:melee": {
                    "constraint_mode": "constrain",
                    "role": "melee_first",
                    "primary_target_unit_id": "target:high",
                    "movement_order": {
                        "intent": "advance_to_charge_lane",
                        "desired_action": "advance",
                        "charge_staging_target_unit_id": "target:high",
                        "intentionally_accept_shooting_ineligible": True,
                    },
                    "charge_order": {
                        "intent": "planned_charge",
                        "primary_target_unit_id": "target:high",
                        "intentionally_skip_shooting": True,
                    },
                    "fight_order": {
                        "intent": "planned_fight",
                        "primary_target_unit_id": "target:high",
                    },
                }
            }
        },
    )
    deployment_orders = game.get_or_create_deployment_order_bundle(player.id)
    prebattle_orders = game.get_or_create_prebattle_order_bundle(player.id)
    tier1 = game.get_or_create_tier1_plan(player.id)
    tier2 = game.get_or_create_tier2_task_bundle(player.id)
    analysis = game.get_or_create_battle_round_plan(player.id).metadata["analysis_snapshot"]

    stage_orders = compile_general_intent_to_commander_orders(
        game,
        custom_general,
        deployment_orders,
        prebattle_orders,
        tier1,
        tier2,
        analysis,
        battle_round=1,
        player_id=player.id,
    ).to_dict()
    push_orders = compile_general_intent_to_commander_orders(
        game,
        custom_general,
        deployment_orders,
        prebattle_orders,
        tier1,
        tier2,
        analysis,
        battle_round=2,
        player_id=player.id,
    ).to_dict()

    stage = stage_orders["unit_orders"]["unit:melee"]
    push = push_orders["unit_orders"]["unit:melee"]
    assert stage["metadata"]["directive_commit_status"] == "staging"
    assert stage["movement_order"]["intent"] == "stage_for_commit"
    assert stage["movement_order"]["desired_action"] == "normal_move"
    assert stage["movement_order"]["intentionally_accept_shooting_ineligible"] is False
    assert stage["charge_order"]["intent"] == "hold"
    assert "primary_target_unit_id" not in stage["charge_order"]
    assert stage["fight_order"]["intent"] == "hold"
    assert "primary_target_unit_id" not in stage["shooting_order"]
    assert push["metadata"]["directive_commit_status"] == "commit"
    assert push["movement_order"]["desired_action"] == "advance"
    assert push["charge_order"]["intent"] == "planned_charge"
    assert push["charge_order"]["primary_target_unit_id"] == "target:high"

    _install_general_plan(game, player, custom_general)
    materialized_stage_plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    materialized_charge = materialized_stage_plan["charge_plan"]["unit_charge_assignments"]["unit:melee"]
    materialized_status = materialized_stage_plan["unit_tasks"]["unit:melee"]["metadata"][
        "commander_constraint_status"
    ]
    assert materialized_status["charge_constraint_status"] == "staged_hold"
    assert "primary_target_unit_id" not in materialized_charge


def test_stage_round_does_not_downshift_hard_replace_order() -> None:
    melee = _Unit(
        "unit:melee",
        keywords=["INFANTRY"],
        wargear=[_Wargear("melee", _Profile(attacks=6, strength=8, ap=-2, damage=2), name="chainaxe")],
    )
    target = _Unit("target:high", wounds=10, oc=4)
    game, player, _opponent = _build_game([melee], [target])
    general = game.get_or_create_general_plan(player.id)
    custom_general = replace(
        general,
        battle_round_directives={1: GeneralRoundDirective(battle_round=1, posture="stage", push_priority=0.2)},
        target_priority_doctrine={
            "unit_order_overrides": {
                "unit:melee": {
                    "constraint_mode": "replace",
                    "role": "melee_first",
                    "primary_target_unit_id": "target:high",
                    "movement_order": {"desired_action": "advance"},
                    "charge_order": {
                        "intent": "planned_charge",
                        "primary_target_unit_id": "target:high",
                    },
                }
            }
        },
    )
    deployment_orders = game.get_or_create_deployment_order_bundle(player.id)
    prebattle_orders = game.get_or_create_prebattle_order_bundle(player.id)
    tier1 = game.get_or_create_tier1_plan(player.id)
    tier2 = game.get_or_create_tier2_task_bundle(player.id)
    analysis = game.get_or_create_battle_round_plan(player.id).metadata["analysis_snapshot"]

    orders = compile_general_intent_to_commander_orders(
        game,
        custom_general,
        deployment_orders,
        prebattle_orders,
        tier1,
        tier2,
        analysis,
        battle_round=1,
        player_id=player.id,
    ).to_dict()

    unit_order = orders["unit_orders"]["unit:melee"]
    assert unit_order["metadata"]["directive_commit_status"] == "commit"
    assert unit_order["movement_order"]["desired_action"] == "advance"
    assert unit_order["charge_order"]["primary_target_unit_id"] == "target:high"


def test_commander_orders_include_enriched_schema_and_explicit_general_overrides() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[_Wargear("ranged", _Profile(attacks=2, strength=8, ap=-2, damage=3), name="lascannon")],
    )
    high_target = _Unit("target:high", wounds=12, oc=5)
    low_target = _Unit("target:low", wounds=2, oc=1)
    game, player, _opponent = _build_game([shooter], [high_target, low_target])
    general = game.get_or_create_general_plan(player.id)
    custom_general = replace(
        general,
        target_priority_doctrine={
            "target_overrides": {
                "target:low": {
                    "intent": "kill",
                    "priority": 0.95,
                    "desired_kill_probability": 0.9,
                    "max_overkill_wounds": 0.25,
                    "preferred_phase": "shooting",
                    "allowed_resource_kinds": ["one_shot_weapon"],
                }
            },
            "unit_order_overrides": {
                "unit:shooter": {
                    "constraint_mode": "constrain",
                    "order_strength": 0.95,
                    "role": "shooting_first",
                    "primary_target_unit_id": "target:low",
                    "backup_target_unit_ids": ["target:high"],
                    "shooting_order": {
                        "primary_target_unit_id": "target:low",
                        "requires_los": True,
                        "max_overkill_wounds": 0.25,
                    },
                }
            },
        },
    )
    deployment_orders = game.get_or_create_deployment_order_bundle(player.id)
    prebattle_orders = game.get_or_create_prebattle_order_bundle(player.id)
    tier1 = game.get_or_create_tier1_plan(player.id)
    tier2 = game.get_or_create_tier2_task_bundle(player.id)
    analysis = game.get_or_create_battle_round_plan(player.id).metadata["analysis_snapshot"]

    commander_orders = compile_general_intent_to_commander_orders(
        game,
        custom_general,
        deployment_orders,
        prebattle_orders,
        tier1,
        tier2,
        analysis,
        battle_round=2,
        player_id=player.id,
    ).to_dict()

    target_order = commander_orders["target_orders"]["target:low"]
    unit_order = commander_orders["unit_orders"]["unit:shooter"]
    assert target_order["intent"] == "kill"
    assert target_order["max_overkill_wounds"] == 0.25
    assert target_order["preferred_phase"] == "shooting"
    assert target_order["allowed_resource_kinds"] == ["one_shot_weapon"]
    assert target_order["metadata"]["explicit_general_override"] is True
    assert unit_order["constraint_mode"] == "constrain"
    assert unit_order["primary_target_unit_id"] == "target:low"
    assert unit_order["backup_target_unit_ids"] == ["target:high"]
    assert unit_order["shooting_order"]["primary_target_unit_id"] == "target:low"
    assert unit_order["shooting_order"]["requires_los"] is True
    assert unit_order["shooting_order"]["expected_damage_by_target"]["target:low"] > 0.0


def test_explicit_general_unit_order_constrains_battle_round_fire_assignment() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[_Wargear("ranged", _Profile(attacks=2, strength=8, ap=-2, damage=3), name="lascannon")],
    )
    high_target = _Unit("target:high", wounds=12, oc=5)
    low_target = _Unit("target:low", wounds=2, oc=1)
    game, player, _opponent = _build_game([shooter], [high_target, low_target])
    general = game.get_or_create_general_plan(player.id)
    custom_general = replace(
        general,
        battle_round_directives={1: GeneralRoundDirective(battle_round=1, posture="push", push_priority=0.9)},
        target_priority_doctrine={
            "unit_order_overrides": {
                "unit:shooter": {
                    "constraint_mode": "replace",
                    "role": "shooting_first",
                    "primary_target_unit_id": "target:low",
                    "shooting_order": {"primary_target_unit_id": "target:low"},
                }
            }
        },
    )
    _install_general_plan(game, player, custom_general)

    plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    fire_assignment = plan["shooting_plan"]["unit_fire_assignments"]["unit:shooter"]
    unit_task = plan["unit_tasks"]["unit:shooter"]

    assert fire_assignment["primary_target_unit_id"] == "target:low"
    assert fire_assignment["metadata"]["commander_constraint_status"]["shooting_constraint_status"] == "applied"
    assert unit_task["metadata"]["commander_constraint_status"]["constraint_mode"] == "replace"


def test_stale_explicit_general_unit_order_falls_back_to_greedy_assignment() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[_Wargear("ranged", _Profile(attacks=2, strength=8, ap=-2, damage=3), name="lascannon")],
    )
    target = _Unit("target:present", wounds=8, oc=3)
    game, player, _opponent = _build_game([shooter], [target])
    general = game.get_or_create_general_plan(player.id)
    custom_general = replace(
        general,
        battle_round_directives={1: GeneralRoundDirective(battle_round=1, posture="push", push_priority=0.9)},
        target_priority_doctrine={
            "unit_order_overrides": {
                "unit:shooter": {
                    "constraint_mode": "constrain",
                    "role": "shooting_first",
                    "primary_target_unit_id": "target:missing",
                    "shooting_order": {"primary_target_unit_id": "target:missing"},
                }
            }
        },
    )
    _install_general_plan(game, player, custom_general)

    plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    fire_assignment = plan["shooting_plan"]["unit_fire_assignments"]["unit:shooter"]

    assert fire_assignment["primary_target_unit_id"] == "target:present"
    assert (
        fire_assignment["metadata"]["commander_constraint_status"]["shooting_constraint_status"]
        == "target_not_in_current_analysis"
    )


def test_commander_constraint_status_stays_out_of_normal_context_but_in_full_plan() -> None:
    shooter = _Unit(
        "unit:shooter",
        wargear=[_Wargear("ranged", _Profile(attacks=2, strength=8, ap=-2, damage=3), name="lascannon")],
    )
    target = _Unit("target:present", wounds=8, oc=3)
    game, player, _opponent = _build_game([shooter], [target])
    general = game.get_or_create_general_plan(player.id)
    custom_general = replace(
        general,
        target_priority_doctrine={
            "unit_order_overrides": {
                "unit:shooter": {
                    "constraint_mode": "replace",
                    "role": "shooting_first",
                    "primary_target_unit_id": "target:present",
                    "shooting_order": {"primary_target_unit_id": "target:present"},
                }
            }
        },
    )
    _install_general_plan(game, player, custom_general)

    full_plan = game.get_or_create_battle_round_plan(player.id).to_dict()
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[DecisionOption.create("Yes", payload={"choice": True})],
        context={"unit_id": "unit:shooter"},
    )

    game.request_decision(request)

    local_slice_keys = [
        "unit_battle_task",
        "commander_movement_task",
        "commander_fire_assignment",
        "commander_charge_assignment",
        "commander_fight_assignment",
    ]
    for key in local_slice_keys:
        assert "commander_constraint_status" not in request.context[key].get("metadata", {})
    assert (
        full_plan["shooting_plan"]["unit_fire_assignments"]["unit:shooter"]["metadata"][
            "commander_constraint_status"
        ]["shooting_constraint_status"]
        == "applied"
    )
    assert (
        full_plan["unit_tasks"]["unit:shooter"]["metadata"]["commander_constraint_status"]["constraint_mode"]
        == "replace"
    )


def test_order_bundle_serialization_is_deterministic_and_context_stays_slim() -> None:
    scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    target = _Unit("target:high", wounds=8)
    game, player, _opponent = _build_game([scout], [target])

    first_deployment = game.get_or_create_deployment_order_bundle(player.id).to_dict()
    first_prebattle = game.get_or_create_prebattle_order_bundle(player.id).to_dict()
    first_commander = game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["commander_order_bundle"]

    assert first_deployment == game.get_or_create_deployment_order_bundle(player.id).to_dict()
    assert first_prebattle == game.get_or_create_prebattle_order_bundle(player.id).to_dict()
    assert first_commander == game.get_or_create_battle_round_plan(player.id).to_dict()["metadata"]["commander_order_bundle"]

    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        "Scout move",
        player_id=player.id,
        options=[DecisionOption.create("Scout", payload={"unit_id": "unit:scout"})],
        context={"unit_id": "unit:scout"},
    )
    before_options = [option.to_dict() for option in request.options]
    before_mask = list(request.mask)

    game.request_decision(request)

    assert request.context["deployment_order_bundle_id"] == first_deployment["order_bundle_id"]
    assert request.context["prebattle_order_bundle_id"] == first_prebattle["order_bundle_id"]
    assert request.context["scout_move_order"]["unit_id"] == "unit:scout"
    assert "deployment_order_bundle" not in request.context
    assert "prebattle_order_bundle" not in request.context
    assert "commander_order_bundle" not in request.context
    assert "general_plan" not in request.context
    assert "deployment_plan" not in request.context
    assert "battle_round_plan" not in request.context
    assert [option.to_dict() for option in request.options] == before_options
    assert request.mask == before_mask


def test_full_compiler_outputs_are_audit_only() -> None:
    scout = _Unit("unit:scout", scout_distance=6.0, deployed=False)
    game, player, _opponent = _build_game([scout], [])
    request = DecisionRequest.create(
        DECISION_SCOUT_MOVE,
        "Scout move",
        player_id=player.id,
        options=[DecisionOption.create("Scout", payload={"unit_id": "unit:scout"})],
        context={
            "unit_id": "unit:scout",
            "include_full_deployment_order_bundle": True,
            "include_full_prebattle_order_bundle": True,
        },
    )

    game.request_decision(request)

    assert request.context["deployment_order_bundle"]["order_bundle_id"] == request.context["deployment_order_bundle_id"]
    assert request.context["prebattle_order_bundle"]["order_bundle_id"] == request.context["prebattle_order_bundle_id"]


def test_non_deployment_context_can_opt_into_full_commander_order_bundle() -> None:
    unit = _Unit("unit:line")
    target = _Unit("target:high", wounds=8)
    game, player, _opponent = _build_game([unit], [target])
    request = DecisionRequest.create(
        DECISION_CONFIRM_YES_NO,
        "Confirm?",
        player_id=player.id,
        options=[DecisionOption.create("Yes", payload={"choice": True})],
        context={"unit_id": "unit:line", "include_full_commander_order_bundle": True},
    )

    game.request_decision(request)

    assert request.context["commander_order_bundle"]["order_bundle_id"] == request.context["commander_order_bundle_id"]
