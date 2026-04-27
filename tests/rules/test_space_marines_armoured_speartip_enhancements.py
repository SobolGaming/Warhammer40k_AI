from __future__ import annotations

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_SELECT_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, BattleRoundPhases, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.enhancement_descriptors import get_enhancement_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
        transport: str = "",
    ):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ADEPTUS ASTARTES"])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "5",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


class _DummyWargear:
    def is_ranged(self) -> bool:
        return True


class _DummyRangedProfile:
    parent_wargear = _DummyWargear()


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
    transport: str = "",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Armoured Speartip")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army, sm_player, enemy_player


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    unit.position = (float(x), float(y), 0.0)
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if alive:
            model.set_location(float(x) + float(idx) * 0.2, float(y), 0.0, 0.0)


def _apply_enhancement(unit: Unit, *, enhancement_id: str, enhancement_name: str) -> None:
    Enhancement(
        id=enhancement_id,
        name=enhancement_name,
        faction_id="SM",
        detachment="Armoured Speartip",
        points=0,
        description="",
    ).apply_to_unit(unit)


def _embark(transport: Unit, passenger: Unit) -> None:
    transport.transport_passengers = [passenger]
    passenger.embarked_in = transport


def _first_option_with(request, predicate):
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if predicate(payload):
            return opt
    return None


def _find_pending_request(game: Game, *, decision_type: str, ability: str = ""):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if not ability:
            return request
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability):
            return request
    return None


def test_armoured_speartip_enhancement_descriptors_exist():
    expected = {
        "000010779002": ("Liberator", "sticky_objective_control"),
        "000010779003": ("Tip of the Spear", "grant_scouts_if_bearer_starts_embarked"),
        "000010779004": (
            "Shock Deployment",
            "grant_ranged_sustained_hits_if_disembarked_from_transport_this_turn",
        ),
        "000010779005": (
            "Armoured Commander",
            "selected_transport_strategic_reserves_setup_round_bonus",
        ),
    }
    for enhancement_id, (name, effect) in expected.items():
        descriptor = get_enhancement_tool_descriptor(enhancement_id=enhancement_id)
        assert descriptor is not None
        assert str(getattr(descriptor, "name", "") or "") == name
        assert str(getattr(descriptor, "effect", "") or "") == effect


def test_liberator_sticky_objective_works_from_heavy_transport_only_while_bearer_alive():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    bearer = _make_unit("Techmarine", keywords=["CHARACTER", "INFANTRY"])
    heavy_transport = _make_unit(
        "Land Raider",
        keywords=["VEHICLE", "TRANSPORT"],
        wounds=16,
        transport="Transport Capacity 12",
    )
    light_transport = _make_unit(
        "Impulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        wounds=11,
        transport="Transport Capacity 6",
    )
    army.add_unit(bearer)
    army.add_unit(heavy_transport)
    army.add_unit(light_transport)
    _set_model_location(bearer, 100.0, 0.0)
    _set_model_location(heavy_transport, 0.0, 0.0)
    _set_model_location(light_transport, 10.0, 0.0)
    game.map.units = [bearer, heavy_transport, light_transport]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer, enhancement_id="000010779002", enhancement_name="Liberator")
    assert heavy_transport.has_keyword("HEAVY TRANSPORT")
    assert not light_transport.has_keyword("HEAVY TRANSPORT")

    objective_point = ObjectivePoint(0.0, 0.0, 0.0, control_radius=3.0)
    game.map.objectives = [
        Objective(
            name="Central Objective",
            category=ObjectiveCategory.PRIMARY,
            points=0,
            description="",
            conditions=lambda _g: False,
            location=objective_point,
        )
    ]

    _embark(heavy_transport, bearer)
    claim_rule = bearer.command_phase_sticky_objective_claim_rule(objective_point)
    assert claim_rule is not None
    assert str(claim_rule.get("source", "") or "") == "armoured_speartip_liberator"

    game.event_system.publish("phase_end", player=player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert objective_point.sticky_controller is player

    _embark(light_transport, bearer)
    light_only_objective = ObjectivePoint(10.0, 0.0, 0.0, control_radius=3.0)
    assert bearer.command_phase_sticky_objective_claim_rule(light_only_objective) is None

    _embark(heavy_transport, bearer)
    bearer.models[0].take_damage(int(getattr(bearer.models[0], "wounds", 0) or 0), game_map=game.map)
    assert bearer.command_phase_sticky_objective_claim_rule(objective_point) is None


def test_tip_of_the_spear_grants_scouts_nine_to_transport_bearer_starts_embarked_in():
    game, army, _enemy_army, _player, _enemy_player = _build_game()
    bearer = _make_unit("Captain", keywords=["CHARACTER", "INFANTRY"])
    transport = _make_unit("Repulsor", keywords=["VEHICLE", "TRANSPORT"], wounds=16)
    non_transport = _make_unit("Predator Destructor", keywords=["VEHICLE"], wounds=11)
    army.add_unit(bearer)
    army.add_unit(transport)
    army.add_unit(non_transport)
    game.map.units = [bearer, transport, non_transport]
    game.rebuild_entity_registry()

    _apply_enhancement(bearer, enhancement_id="000010779003", enhancement_name="Tip of the Spear")
    _embark(transport, bearer)
    bearer._apply_aggressive_deployment_scouts(transport)

    has_scout, distance = transport.has_scout()
    assert bool(has_scout)
    assert int(distance) == 9
    assert bool(transport.special_rules.get("enhancement_armoured_speartip_tip_of_the_spear_active"))

    bearer._apply_aggressive_deployment_scouts(non_transport)
    has_non_transport_scout, _distance = non_transport.has_scout()
    assert not bool(has_non_transport_scout)


def test_shock_deployment_grants_ranged_sustained_hits_after_transport_disembark_in_shooting_phase():
    game, army, _enemy_army, _player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    aggressors = _make_unit("Aggressor Squad", keywords=["GRAVIS", "INFANTRY"], model_count=3)
    target = _make_unit("Enemy Rhino", keywords=["VEHICLE"], faction_keywords=["HERETIC ASTARTES"], wounds=10)
    army.add_unit(aggressors)
    _enemy_army.add_unit(target)
    game.map.units = [aggressors, target]
    game.rebuild_entity_registry()

    _apply_enhancement(aggressors, enhancement_id="000010779004", enhancement_name="Shock Deployment")
    profile = _DummyRangedProfile()

    before = aggressors.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=aggressors.models[0],
        weapon_profile=profile,
    )
    assert int(before.get("sustained_hits_value", 0) or 0) == 0

    aggressors.round_state.disembarked_this_round = True
    aggressors.round_state.disembarked_from_transport_id = "transport-1"
    after = aggressors.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=aggressors.models[0],
        weapon_profile=profile,
    )
    assert int(after.get("sustained_hits_value", 0) or 0) == 1

    melee = aggressors.get_attack_keyword_bonuses(
        target=target,
        attack_type="melee",
        model=aggressors.models[0],
        weapon_profile=profile,
    )
    assert int(melee.get("sustained_hits_value", 0) or 0) == 0


def test_armoured_commander_decision_grants_selected_transport_temporary_reserves_round_bonus():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    source = _make_unit("Captain", keywords=["CHARACTER", "INFANTRY"])
    reserve_transport = _make_unit(
        "Repulsor",
        keywords=["VEHICLE", "TRANSPORT"],
        wounds=16,
        transport="Transport Capacity 12",
    )
    reserve_transport.reserve_status = "strategic_reserves"
    reserve_transport._started_in_reserves = True
    reserve_transport.deployed = False
    ineligible_reserve = _make_unit("Predator Destructor", keywords=["VEHICLE"], wounds=11)
    ineligible_reserve.reserve_status = "strategic_reserves"
    ineligible_reserve._started_in_reserves = True
    ineligible_reserve.deployed = False

    army.add_unit(source)
    army.add_unit(reserve_transport)
    army.add_unit(ineligible_reserve)
    _set_model_location(source, 0.0, 0.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010779005", enhancement_name="Armoured Commander")
    assert not reserve_transport.can_arrive_from_reserves(1)

    queued = army.space_marines_detachments.queue_armoured_speartip_armoured_commander_requests(
        game=game,
        player=player,
    )
    assert bool(queued)
    request = _find_pending_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="space_marines_armoured_speartip_armoured_commander",
    )
    assert request is not None
    candidate_ids = set(str(value or "") for value in list(request.context.get("candidate_unit_ids", []) or []))
    assert str(get_entity_id(reserve_transport)) in candidate_ids
    assert str(get_entity_id(ineligible_reserve)) not in candidate_ids

    target_option = _first_option_with(
        request,
        lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(reserve_transport)),
    )
    assert target_option is not None
    result = resolve_decision_command(game, request, target_option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False))

    assert bool(reserve_transport.special_rules.get("enhancement_armoured_speartip_armoured_commander_active"))
    assert reserve_transport.can_arrive_from_reserves(1)
    assert int(reserve_transport.get_strategic_reserves_setup_turn(game=game, current_turn=1)) == 2
    select_request = _find_pending_request(game, decision_type=DECISION_SELECT_UNIT)
    assert select_request is not None
    assert str(get_entity_id(reserve_transport)) in list(select_request.context.get("allowed_unit_ids", []) or [])

    army.space_marines_detachments.on_phase_end(BattleRoundPhases.MOVEMENT_PHASE, player, game=game)
    assert not bool(reserve_transport.special_rules.get("enhancement_armoured_speartip_armoured_commander_active"))
    assert not reserve_transport.can_arrive_from_reserves(1)


def test_armoured_commander_rejects_invalid_decision_target_payload():
    game, army, _enemy_army, player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    source = _make_unit("Captain", keywords=["CHARACTER", "INFANTRY"])
    reserve_transport = _make_unit("Repulsor", keywords=["VEHICLE", "TRANSPORT"], wounds=16)
    reserve_transport.reserve_status = "strategic_reserves"
    reserve_transport._started_in_reserves = True
    reserve_transport.deployed = False
    invalid_target = _make_unit("Predator Destructor", keywords=["VEHICLE"], wounds=11)
    invalid_target.reserve_status = "strategic_reserves"
    invalid_target._started_in_reserves = True
    invalid_target.deployed = False

    army.add_unit(source)
    army.add_unit(reserve_transport)
    army.add_unit(invalid_target)
    _set_model_location(source, 0.0, 0.0)
    game.map.units = [source]
    game.rebuild_entity_registry()

    _apply_enhancement(source, enhancement_id="000010779005", enhancement_name="Armoured Commander")
    assert bool(
        army.space_marines_detachments.queue_armoured_speartip_armoured_commander_requests(
            game=game,
            player=player,
        )
    )
    request = _find_pending_request(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="space_marines_armoured_speartip_armoured_commander",
    )
    assert request is not None
    valid_option = _first_option_with(
        request,
        lambda payload: str(payload.get("target_unit_id", "") or "") == str(get_entity_id(reserve_transport)),
    )
    assert valid_option is not None
    valid_option.payload["target_unit_id"] = str(get_entity_id(invalid_target))

    result = resolve_decision_command(game, request, valid_option.option_id, player_id=player.id)
    assert bool(getattr(result, "ok", False)) is False
    assert not bool(invalid_target.special_rules.get("enhancement_armoured_speartip_armoured_commander_active"))
