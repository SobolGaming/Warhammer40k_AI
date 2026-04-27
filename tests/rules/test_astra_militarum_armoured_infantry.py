from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry, _validate_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, ORDER_ON_MY_SIGNAL
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _Datasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
        wounds: int = 6,
        move: str = "10",
        transport: str = "",
    ):
        self.id = f"ds-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Astra Militarum"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["ASTRA MILITARUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": str(move),
                "T": "6",
                "Sv": "3",
                "W": str(wounds),
                "Ld": "6",
                "OC": "2",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [
            {
                "name": getattr(ability, "name", ""),
                "description": getattr(ability, "description", ""),
                "type": "Datasheet",
                "parameter": "",
            }
            for ability in list(abilities or [])
        ]
        self.loadout = "This model is equipped with: nothing"
        self.transport = str(transport or "")
        self.attached_to = []
        self.attached_to_names = []


def _ability(name: str, description: str = ""):
    return SimpleNamespace(name=name, description=description or name)


def _make_unit(
    name: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    wounds: int = 6,
    move: str = "10",
    transport: str = "",
) -> Unit:
    unit = Unit(
        _Datasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
            move=move,
            transport=transport,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _officer(name: str = "Command Squad") -> Unit:
    return _make_unit(
        name,
        keywords=["INFANTRY", "OFFICER"],
        abilities=[
            _ability("Voice of Command", "Officer models with this ability can issue Orders."),
            _ability("Orders", "This Officer can issue 1 Order to a Regiment unit."),
        ],
    )


def _build_game(detachment_type: str = "Armoured Infantry"):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    am_army = Army.with_detachment("Astra Militarum", detachment_type=detachment_type)
    am_army.faction_id = "AM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "ENEMY"
    am_player = Player("Astra Militarum", control=PlayerControl.REMOTE, army=am_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(am_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, am_player, enemy_player, am_army, enemy_army


def _place_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    if unit not in game.map.units:
        game.map.units.append(unit)


def _first_confirmation(game: Game, *, source: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CONFIRM_YES_NO:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("reactive_move_source", "") or "") == source:
            return request
    return None


def _find_request(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == str(decision_type):
            return request
    return None


def _pending_by_name(stratagems, name: str):
    wanted = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == wanted:
            return reaction
    return None


def _finalize_game(game: Game, *armies: Army, players: list[Player]) -> None:
    game.rebuild_entity_registry()
    for army in armies:
        army.configure_rule_managers(force=True)
    refresh = getattr(game, "refresh_rule_subscribers", None)
    if callable(refresh):
        refresh()
    for player in players:
        player.stratagems.refresh_available()


def _exemplary_officer() -> Enhancement:
    return Enhancement(
        id="000010791002",
        name="Exemplary Officer",
        faction_id="AM",
        detachment="Armoured Infantry",
        points=20,
        description=(
            "Infantry Officer model only. Each time the bearer issues an Order to its own unit, "
            "you can select up to two other Platoon units within 3\" of the bearer's unit. "
            "That Order is also issued to each of those units."
        ),
    )


def _master_manoeuvrist() -> Enhancement:
    return Enhancement(
        id="000010791003",
        name="Master Manoeuvrist",
        faction_id="AM",
        detachment="Armoured Infantry",
        points=15,
        description=(
            "Infantry Officer model only. At the end of your opponent's Fight phase, if the bearer's unit is not "
            "within Engagement Range of one or more enemy units and every model in that unit is within 3\" of an "
            "Astra Militarum Transport from your army, it can embark within that TRANSPORT."
        ),
    )


def _omnissian_unguents() -> Enhancement:
    return Enhancement(
        id="000010791004",
        name="Omnissian Unguents (Aura)",
        faction_id="AM",
        detachment="Armoured Infantry",
        points=10,
        description=(
            "Astra Militarum Tech-Priest Enginseer model only. While a friendly Armoured Skirmisher unit is "
            "within 3\" of the bearer, that unit has the Feel No Pain 5+ ability."
        ),
    )


def _grand_strategist() -> Enhancement:
    return Enhancement(
        id="000010791005",
        name="Grand Strategist",
        faction_id="AM",
        detachment="Armoured Infantry",
        points=15,
        description=(
            "Officer model only. After both players have deployed their armies, if the bearer's unit "
            "(or any Transport it is embarked within) is on the battlefield, select up to two units with "
            "the Regiment or Squadron keywords from your army and redeploy them. When doing so, you can "
            "set those units up in Strategic Reserves, regardless of how many units are already in Strategic Reserves."
        ),
    )


def _find_quarry_request(game: Game, *, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == ability:
            return request
    return None


def _find_redeploy_request(game: Game, *, ability_name: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") != "aeldari_guileful_strategist":
            continue
        if str(context.get("ability_name", "") or "") == str(ability_name):
            return request
    return None


def _option_with_selected_units(request, selected_units):
    selected_ids = [str(get_entity_id(unit) or "") for unit in selected_units]
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if list(payload.get("selected_unit_ids", []) or []) == selected_ids:
            return option
    return None


def _redeploy_option(request, *, target_unit: Unit, action: str):
    target_id = str(get_entity_id(target_unit) or "")
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") != target_id:
            continue
        if str(payload.get("redeploy_action", "") or "").strip().lower() != action_key:
            continue
        return option
    return None


def test_armoured_infantry_grants_armoured_skirmisher_only_to_eligible_squadrons():
    army = Army.with_detachment("Astra Militarum", detachment_type="Armoured Infantry")
    army.faction_id = "AM"
    sentinel = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    artillery = _make_unit("Field Ordnance Battery", keywords=["VEHICLE", "SQUADRON", "ARTILLERY"], wounds=6)
    russ = _make_unit("Leman Russ Battle Tank", keywords=["VEHICLE", "SQUADRON"], wounds=13)

    army.add_unit(sentinel)
    army.add_unit(artillery)
    army.add_unit(russ)

    assert sentinel.has_any_keyword("ARMOURED")
    assert sentinel.has_any_keyword("SKIRMISHER")
    assert not artillery.has_any_keyword("ARMOURED")
    assert not artillery.has_any_keyword("SKIRMISHER")
    assert not russ.has_any_keyword("ARMOURED")
    assert not russ.has_any_keyword("SKIRMISHER")


def test_armoured_infantry_burst_of_speed_descriptor_registered():
    by_id = get_stratagem_tool_descriptor(stratagem_id="000010792004")

    assert by_id is not None
    assert by_id.name == "Burst of Speed"
    assert by_id.effect == "reactive_normal_move_d6"
    assert by_id.effect_params["requires_not_remained_stationary"] is True
    assert by_id.effect_params["requires_not_arrived_from_reserves_this_phase"] is True


def test_armoured_infantry_combined_fire_descriptor_registered():
    by_id = get_stratagem_tool_descriptor(stratagem_id="000010792006")

    assert by_id is not None
    assert by_id.name == "Combined Fire"
    assert by_id.effect == "post_shoot_no_cover_and_armoured_skirmisher_strength_bonus"
    assert by_id.effect_params["target_cannot_have_benefit_of_cover"] is True
    assert by_id.effect_params["attack_type"] == "ranged"
    assert by_id.effect_params["strength_bonus"] == 2


def test_armoured_infantry_burst_of_speed_queues_end_movement_phase_reactive_move():
    game, am_player, _enemy_player, army, enemy_army = _build_game()
    moved_unit = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    stationary_unit = _make_unit("Heavy Weapon Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    reserves_unit = _make_unit("Kasrkin", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    for unit in (moved_unit, stationary_unit, reserves_unit):
        army.add_unit(unit)
        _place_unit(game, unit, 10.0 + len(game.map.units), 10.0)
    moved_unit.round_state.remained_stationary_this_round = False
    moved_unit.round_state.moved_this_round = True
    stationary_unit.round_state.remained_stationary_this_round = True
    reserves_unit.round_state.remained_stationary_this_round = False
    reserves_unit.arrived_from_reserves_this_turn = True
    am_player.command_points = 10
    _finalize_game(game, army, enemy_army, players=[am_player, _enemy_player])

    game.current_player_index = game.players.index(am_player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.event_system.publish("phase_end", player=am_player, phase=game.phase)

    pending = _pending_by_name(am_player.stratagems, "BURST OF SPEED")
    assert pending is not None
    assert pending.get("candidates") == [moved_unit]

    with patch("warhammer40k_ai.rules.stratagems_astra_militarum.get_roll", return_value=5):
        ok = am_player.stratagems.use("BURST OF SPEED", unit=moved_unit, phase_name="Movement phase", dequeue=True)

    assert ok is True
    assert int(am_player.command_points or 0) == 9
    request = _find_request(game, DECISION_MOVE_UNIT)
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert context.get("reactive_move_source") == "BURST OF SPEED"
    assert context.get("reactive_move_kind") == "astra_militarum_armoured_infantry_burst_of_speed"
    assert context.get("reactive_move_movement_type") == "armoured_infantry_burst_of_speed"
    assert context.get("unit_id") == get_entity_id(moved_unit)
    assert int(context.get("max_distance", 0) or 0) == 5


def test_armoured_infantry_burst_of_speed_rejects_stationary_or_reserve_arrivals():
    game, am_player, enemy_player, army, enemy_army = _build_game()
    moved_unit = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    stationary_unit = _make_unit("Heavy Weapon Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    reserves_unit = _make_unit("Kasrkin", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    for unit in (moved_unit, stationary_unit, reserves_unit):
        army.add_unit(unit)
        _place_unit(game, unit, 10.0 + len(game.map.units), 10.0)
    moved_unit.round_state.remained_stationary_this_round = False
    moved_unit.round_state.moved_this_round = True
    stationary_unit.round_state.remained_stationary_this_round = True
    reserves_unit.round_state.remained_stationary_this_round = False
    reserves_unit.arrived_from_reserves_this_turn = True
    am_player.command_points = 10
    _finalize_game(game, army, enemy_army, players=[am_player, enemy_player])

    game.current_player_index = game.players.index(am_player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

    assert am_player.stratagems.use("BURST OF SPEED", unit=stationary_unit, phase_name="Movement phase") is False
    assert am_player.stratagems.use("BURST OF SPEED", unit=reserves_unit, phase_name="Movement phase") is False
    assert int(am_player.command_points or 0) == 10


def test_armoured_infantry_combined_fire_queues_hit_enemy_and_marks_target():
    game, am_player, enemy_player, army, enemy_army = _build_game()
    shooter = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    other_shooter = _make_unit("Second Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    infantry = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=1)
    enemy_not_hit = _make_unit("Enemy Not Hit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=1)
    for unit in (shooter, other_shooter, infantry):
        army.add_unit(unit)
    for unit in (enemy, enemy_not_hit):
        enemy_army.add_unit(unit)
    _place_unit(game, shooter, 10.0, 10.0)
    _place_unit(game, other_shooter, 12.0, 10.0)
    _place_unit(game, infantry, 14.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    _place_unit(game, enemy_not_hit, 22.0, 10.0)
    am_player.command_points = 10
    _finalize_game(game, army, enemy_army, players=[am_player, enemy_player])

    game.current_player_index = game.players.index(am_player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    shooter.round_state.shot_this_round = True
    game.event_system.publish("unit_shooting_resolved", attacker_unit=shooter, hits_by_target={enemy: 2, enemy_not_hit: 0})

    pending = _pending_by_name(am_player.stratagems, "COMBINED FIRE")
    assert pending is not None
    assert pending.get("candidates") == [enemy]
    assert am_player.stratagems.use("COMBINED FIRE", unit=shooter, phase_name="Shooting phase", dequeue=True) is True
    assert int(am_player.command_points or 0) == 9

    request = _find_quarry_request(game, ability="armoured_infantry_combined_fire")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert context.get("attacker_unit_id") == get_entity_id(shooter)
    assert context.get("candidate_unit_ids") == [get_entity_id(enemy)]
    option = next(
        opt for opt in request.options
        if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or "")) == get_entity_id(enemy)
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=am_player.id,
        option_id=option.option_id,
        payload={},
    )
    assert _validate_choose_quarry(game, request, result) == ()
    resolve_decision_command(game, request, option.option_id, player_id=am_player.id)

    assert enemy.special_rules.get("post_shoot_no_cover_active") is True
    assert enemy.special_rules.get("armoured_infantry_combined_fire_active") is True
    mgr = army.astra_militarum_detachments
    assert mgr.armoured_infantry_combined_fire_strength_bonus(
        other_shooter.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    ) == (2, "COMBINED FIRE")
    assert mgr.armoured_infantry_combined_fire_strength_bonus(
        infantry.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    ) == (0, "")
    assert mgr.armoured_infantry_combined_fire_strength_bonus(
        other_shooter.models[0],
        enemy_not_hit,
        attack_type="ranged",
        game=game,
    ) == (0, "")

    weapon = Wargear(
        {
            "name": "Multilaser",
            "type": "Ranged",
            "range": "36",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    wound = weapon.profiles["default"]._wound_target_with_tracking(
        enemy,
        other_shooter.models[0],
        {"benefit_of_cover": True},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(wound.get("wound"))
    assert any("COMBINED FIRE" in str(item).upper() for item in list(wound.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=am_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert not bool(enemy.special_rules.get("armoured_infantry_combined_fire_active"))
    assert not bool(enemy.special_rules.get("post_shoot_no_cover_active"))
    assert mgr.armoured_infantry_combined_fire_strength_bonus(
        other_shooter.models[0],
        enemy,
        attack_type="ranged",
        game=game,
    ) == (0, "")


def test_armoured_infantry_combined_fire_rejects_non_skirmisher_or_invalid_enemy_selection():
    game, am_player, enemy_player, army, enemy_army = _build_game()
    shooter = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    infantry = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=1)
    unhit_enemy = _make_unit("Unhit Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=1)
    for unit in (shooter, infantry):
        army.add_unit(unit)
    for unit in (enemy, unhit_enemy):
        enemy_army.add_unit(unit)
    _place_unit(game, shooter, 10.0, 10.0)
    _place_unit(game, infantry, 12.0, 10.0)
    _place_unit(game, enemy, 20.0, 10.0)
    _place_unit(game, unhit_enemy, 22.0, 10.0)
    am_player.command_points = 10
    _finalize_game(game, army, enemy_army, players=[am_player, enemy_player])

    game.current_player_index = game.players.index(am_player)
    game.current_player_idx = game.current_player_index
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    infantry.round_state.shot_this_round = True
    game.event_system.publish("unit_shooting_resolved", attacker_unit=infantry, hits_by_target={enemy: 1})
    assert _pending_by_name(am_player.stratagems, "COMBINED FIRE") is None

    shooter.round_state.shot_this_round = True
    assert am_player.stratagems.use(
        "COMBINED FIRE",
        unit=shooter,
        candidates=[enemy],
        enemy_unit=unhit_enemy,
        phase_name="Shooting phase",
    ) is False
    assert int(am_player.command_points or 0) == 10

    request = _find_quarry_request(game, ability="armoured_infantry_combined_fire")
    assert request is None
    fake_request = _find_request(game, DECISION_CHOOSE_QUARRY)
    if fake_request is None:
        from warhammer40k_ai.engine.decisions import DecisionRequest

        fake_request = DecisionRequest.create(
            DECISION_CHOOSE_QUARRY,
            "COMBINED FIRE: select an enemy unit hit by that unit.",
            player_id=am_player.id,
            options=[
                DecisionOption.create(
                    "Unhit Enemy",
                    payload={"target_unit_id": get_entity_id(unhit_enemy)},
                )
            ],
            context={
                "ability": "armoured_infantry_combined_fire",
                "ability_name": "COMBINED FIRE",
                "attacker_unit_id": get_entity_id(shooter),
                "candidate_unit_ids": [get_entity_id(enemy)],
            },
        )
    invalid = DecisionResult(
        decision_id=fake_request.decision_id,
        player_id=am_player.id,
        option_id=fake_request.options[0].option_id,
        payload={},
    )
    errors = _validate_choose_quarry(game, fake_request, invalid)
    assert errors == ("Combined Fire target is not in this request's candidate list.",)


def test_squadron_command_extends_orders_and_on_my_signal_targeting():
    game, _am_player, _enemy_player, army, _enemy_army = _build_game()
    officer = _officer()
    squadron = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    regiment = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    army.add_unit(officer)
    army.add_unit(squadron)
    army.add_unit(regiment)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, squadron, 14.0, 10.0)
    _place_unit(game, regiment, 12.0, 10.0)
    game.rebuild_entity_registry()

    available = {order.key for order in army.voice_of_command.get_available_orders(officer)}
    assert ORDER_ON_MY_SIGNAL.key in available

    move_targets = army.voice_of_command.get_eligible_targets(officer, game=game, order_key=ORDER_MOVE.key)
    assert squadron in move_targets

    on_signal_targets = army.voice_of_command.get_eligible_targets(
        officer,
        game=game,
        order_key=ORDER_ON_MY_SIGNAL.key,
    )
    assert on_signal_targets == [squadron]

    assert army.voice_of_command.issue_order(game, officer, squadron, ORDER_ON_MY_SIGNAL.key) is True
    assert squadron.special_rules.get("voice_of_command_order_key") == ORDER_ON_MY_SIGNAL.key
    assert squadron.special_rules.get("voice_of_command_on_my_signal_active") is True


def test_on_my_signal_reactive_move_triggers_for_normal_or_advance_only():
    game, _am_player, enemy_player, army, enemy_army = _build_game()
    officer = _officer()
    squadron = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7, move="10")
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=1,
        move="6",
    )
    army.add_unit(officer)
    army.add_unit(squadron)
    enemy_army.add_unit(enemy)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, squadron, 14.0, 10.0)
    _place_unit(game, enemy, 22.0, 10.0)
    game.rebuild_entity_registry()
    game.refresh_rule_subscribers()

    assert army.voice_of_command.issue_order(game, officer, squadron, ORDER_ON_MY_SIGNAL.key) is True

    game.current_player_index = game.players.index(enemy_player)
    game.phase = SimpleNamespace(name="MOVEMENT_PHASE")
    game.event_system.publish("unit_move_ended", unit=enemy, action="fall_back")
    assert _first_confirmation(game, source="On My Signal") is None

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    request = _first_confirmation(game, source="On My Signal")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert context.get("reactive_move_kind") == "loping_speed"
    assert context.get("reactive_move_movement_type") == "loping_speed"
    assert context.get("reactive_move_unit_id") == get_entity_id(squadron)
    assert context.get("reactive_move_moving_unit_id") == get_entity_id(enemy)
    assert int(context.get("reactive_move_range", 0) or 0) == 9


def test_on_my_signal_is_not_available_outside_armoured_infantry():
    game, _am_player, _enemy_player, army, _enemy_army = _build_game(detachment_type="Combined Arms")
    officer = _officer()
    squadron = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    army.add_unit(officer)
    army.add_unit(squadron)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, squadron, 14.0, 10.0)

    available = {order.key for order in army.voice_of_command.get_available_orders(officer)}
    assert ORDER_ON_MY_SIGNAL.key not in available
    assert army.voice_of_command.issue_order(game, officer, squadron, ORDER_ON_MY_SIGNAL.key) is False


def test_exemplary_officer_spreads_own_unit_order_to_up_to_two_nearby_platoon_units():
    game, am_player, _enemy_player, army, _enemy_army = _build_game()
    officer = _officer("Platoon Commander")
    officer.keywords.extend(["REGIMENT", "PLATOON"])
    platoon_a = _make_unit("Infantry Squad A", keywords=["INFANTRY", "PLATOON", "REGIMENT"], wounds=1)
    platoon_b = _make_unit("Infantry Squad B", keywords=["INFANTRY", "PLATOON", "REGIMENT"], wounds=1)
    far_platoon = _make_unit("Far Infantry", keywords=["INFANTRY", "PLATOON", "REGIMENT"], wounds=1)
    non_platoon = _make_unit("Command Vehicle", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    for unit in (officer, platoon_a, platoon_b, far_platoon, non_platoon):
        army.add_unit(unit)
    _exemplary_officer().apply_to_unit(officer)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, platoon_a, 12.0, 10.0)
    _place_unit(game, platoon_b, 10.0, 12.0)
    _place_unit(game, far_platoon, 18.0, 10.0)
    _place_unit(game, non_platoon, 11.0, 10.0)
    game.rebuild_entity_registry()

    assert army.voice_of_command.issue_order(
        game,
        officer,
        officer,
        ORDER_MOVE.key,
        phase_name="COMMAND_PHASE",
    ) is True
    assert officer.special_rules.get("voice_of_command_order_key") == ORDER_MOVE.key

    request = _find_quarry_request(game, ability="exemplary_officer_order_spread")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    candidate_ids = list(context.get("candidate_unit_ids") or [])
    assert set(candidate_ids) == {get_entity_id(platoon_a), get_entity_id(platoon_b)}
    unit_by_id = {get_entity_id(platoon_a): platoon_a, get_entity_id(platoon_b): platoon_b}
    selected_units = [unit_by_id[unit_id] for unit_id in candidate_ids]
    option = _option_with_selected_units(request, selected_units)
    assert option is not None
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=am_player.id,
        option_id=option.option_id,
        payload={},
    )
    assert _validate_choose_quarry(game, request, result) == ()
    applied = _apply_choose_quarry(game, request, result)

    assert applied == selected_units
    assert platoon_a.special_rules.get("voice_of_command_order_key") == ORDER_MOVE.key
    assert platoon_b.special_rules.get("voice_of_command_order_key") == ORDER_MOVE.key
    assert far_platoon.special_rules.get("voice_of_command_order_key") is None
    assert non_platoon.special_rules.get("voice_of_command_order_key") is None


def test_exemplary_officer_skip_and_non_own_unit_order_do_not_apply_extra_orders():
    game, am_player, _enemy_player, army, _enemy_army = _build_game()
    officer = _officer("Platoon Commander")
    officer.keywords.extend(["REGIMENT", "PLATOON"])
    target = _make_unit("Target Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    nearby_platoon = _make_unit("Nearby Platoon", keywords=["INFANTRY", "PLATOON", "REGIMENT"], wounds=1)
    for unit in (officer, target, nearby_platoon):
        army.add_unit(unit)
    _exemplary_officer().apply_to_unit(officer)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, target, 12.0, 10.0)
    _place_unit(game, nearby_platoon, 11.0, 10.0)
    game.rebuild_entity_registry()

    assert army.voice_of_command.issue_order(
        game,
        officer,
        target,
        ORDER_MOVE.key,
        phase_name="COMMAND_PHASE",
    ) is True
    assert _find_quarry_request(game, ability="exemplary_officer_order_spread") is None

    officer.special_rules.clear()
    _exemplary_officer().apply_to_unit(officer)
    target.special_rules.clear()
    nearby_platoon.special_rules.clear()
    assert army.voice_of_command.issue_order(
        game,
        officer,
        officer,
        ORDER_MOVE.key,
        phase_name="COMMAND_PHASE",
    ) is True
    request = _find_quarry_request(game, ability="exemplary_officer_order_spread")
    assert request is not None
    skip_option = next(option for option in request.options if (option.payload or {}).get("action") == "skip")
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=am_player.id,
        option_id=skip_option.option_id,
        payload={},
    )
    assert _validate_choose_quarry(game, request, result) == ()
    assert _apply_choose_quarry(game, request, result) == []
    assert nearby_platoon.special_rules.get("voice_of_command_order_key") is None


def test_master_manoeuvrist_queues_opponent_fight_phase_embark_and_resolves_transport_choice():
    game, am_player, enemy_player, army, _enemy_army = _build_game()
    officer = _officer("Mobile Commander")
    officer.keywords.extend(["REGIMENT", "PLATOON"])
    transport = _make_unit(
        "Chimera",
        keywords=["Transport", "VEHICLE"],
        wounds=11,
        transport="Transport Capacity: 12 Astra Militarum Infantry models",
    )
    army.add_unit(officer)
    army.add_unit(transport)
    _master_manoeuvrist().apply_to_unit(officer)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, transport, 12.0, 10.0)
    game.current_player_index = game.players.index(enemy_player)
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.rebuild_entity_registry()

    game._on_phase_end_transport_end_of_fight_embark(player=enemy_player, phase=game.phase)

    request = _find_quarry_request(game, ability="master_manoeuvrist_embark")
    assert request is not None
    context = dict(getattr(request, "context", {}) or {})
    assert context.get("target_unit_id") == get_entity_id(officer)
    assert context.get("candidate_transport_ids") == [get_entity_id(transport)]
    option = next(
        opt for opt in request.options
        if str((opt.payload or {}).get("transport_id", "") or "") == get_entity_id(transport)
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        player_id=am_player.id,
        option_id=option.option_id,
        payload={},
    )
    assert _validate_choose_quarry(game, request, result) == ()
    _apply_choose_quarry(game, request, result)

    assert officer.embarked_in is transport
    assert officer in transport.transport_passengers
    assert officer not in game.map.units


def test_master_manoeuvrist_does_not_queue_when_engaged_or_active_player_owns_bearer():
    game, _am_player, enemy_player, army, enemy_army = _build_game()
    officer = _officer("Mobile Commander")
    officer.keywords.extend(["REGIMENT", "PLATOON"])
    transport = _make_unit(
        "Chimera",
        keywords=["Transport", "VEHICLE"],
        wounds=11,
        transport="Transport Capacity: 12 Astra Militarum Infantry models",
    )
    enemy = _make_unit("Enemy", keywords=["INFANTRY"], faction_keywords=["ENEMY"], wounds=1)
    army.add_unit(officer)
    army.add_unit(transport)
    enemy_army.add_unit(enemy)
    _master_manoeuvrist().apply_to_unit(officer)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, transport, 12.0, 10.0)
    _place_unit(game, enemy, 10.5, 10.0)
    game.current_player_index = game.players.index(enemy_player)
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    game.rebuild_entity_registry()

    game._on_phase_end_transport_end_of_fight_embark(player=enemy_player, phase=game.phase)
    assert _find_quarry_request(game, ability="master_manoeuvrist_embark") is None

    for model in list(getattr(enemy, "models", []) or []):
        model.set_location(30.0, 30.0, 0.0, 0.0)
    game._on_phase_end_transport_end_of_fight_embark(player=army.player, phase=game.phase)
    assert _find_quarry_request(game, ability="master_manoeuvrist_embark") is None


def test_omnissian_unguents_grants_fnp_to_nearby_armoured_skirmisher_units_only():
    game, _am_player, _enemy_player, army, _enemy_army = _build_game()
    enginseer = _make_unit("Tech-Priest Enginseer", keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST ENGINSEER"])
    near_sentinel = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    far_sentinel = _make_unit("Far Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    artillery = _make_unit("Field Ordnance Battery", keywords=["VEHICLE", "SQUADRON", "ARTILLERY"], wounds=6)
    for unit in (enginseer, near_sentinel, far_sentinel, artillery):
        army.add_unit(unit)
    _omnissian_unguents().apply_to_unit(enginseer)
    _place_unit(game, enginseer, 10.0, 10.0)
    _place_unit(game, near_sentinel, 11.0, 10.0)
    _place_unit(game, far_sentinel, 20.0, 10.0)
    _place_unit(game, artillery, 11.0, 11.0)
    game.rebuild_entity_registry()

    assert near_sentinel.has_any_keyword("ARMOURED")
    assert near_sentinel.has_any_keyword("SKIRMISHER")
    assert (5, None) in list(near_sentinel.has_feel_no_pain(target_model=near_sentinel.models[0]) or [])
    assert (5, None) not in list(far_sentinel.has_feel_no_pain(target_model=far_sentinel.models[0]) or [])
    assert not artillery.has_any_keyword("ARMOURED")
    assert (5, None) not in list(artillery.has_feel_no_pain(target_model=artillery.models[0]) or [])


def test_omnissian_unguents_fnp_stops_when_bearer_is_not_alive():
    game, _am_player, _enemy_player, army, _enemy_army = _build_game()
    enginseer = _make_unit("Tech-Priest Enginseer", keywords=["INFANTRY", "CHARACTER", "TECH-PRIEST ENGINSEER"])
    sentinel = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    army.add_unit(enginseer)
    army.add_unit(sentinel)
    _omnissian_unguents().apply_to_unit(enginseer)
    _place_unit(game, enginseer, 10.0, 10.0)
    _place_unit(game, sentinel, 11.0, 10.0)
    game.rebuild_entity_registry()

    assert (5, None) in list(sentinel.has_feel_no_pain(target_model=sentinel.models[0]) or [])

    enginseer.models[0].wounds = 0
    assert (5, None) not in list(sentinel.has_feel_no_pain(target_model=sentinel.models[0]) or [])


def test_armoured_infantry_grand_strategist_redeploys_regiment_or_squadron_only():
    game, am_player, enemy_player, army, _enemy_army = _build_game()
    game.attacker_index = game.players.index(am_player)
    game.defender_index = game.players.index(enemy_player)
    officer = _officer("Armoured Infantry Commander")
    regiment = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    squadron = _make_unit("Scout Sentinel", keywords=["VEHICLE", "SQUADRON"], wounds=7)
    ineligible = _make_unit("Munitorum Servitors", keywords=["INFANTRY"], wounds=1)
    for unit in (officer, regiment, squadron, ineligible):
        army.add_unit(unit)
    _grand_strategist().apply_to_unit(officer)
    _place_unit(game, officer, 10.0, 10.0)
    _place_unit(game, regiment, 12.0, 10.0)
    _place_unit(game, squadron, 14.0, 10.0)
    _place_unit(game, ineligible, 16.0, 10.0)
    game.rebuild_entity_registry()

    assert officer.has_redeploy() == (True, 2, True)
    cache = dict(getattr(officer, "_ability_cache", {}) or {})
    assert cache.get("redeploy_filter_any_groups") == [["REGIMENT"], ["SQUADRON"]]
    assert bool(cache.get("redeploy_requires_source_on_battlefield", False))
    assert bool(cache.get("redeploy_allow_embarked_transport_on_battlefield", False))
    assert bool(cache.get("redeploy_strategic_reserves_ignore_current_unit_count_limit", False))

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(game, ability_name="Grand Strategist")
    assert request is not None
    target_ids = {
        str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for option in list(getattr(request, "options", []) or [])
        if str((dict(getattr(option, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    assert get_entity_id(regiment) in target_ids
    assert get_entity_id(squadron) in target_ids
    assert get_entity_id(ineligible) not in target_ids

    option = _redeploy_option(request, target_unit=regiment, action="strategic_reserves")
    assert option is not None
    resolve_decision_command(game, request, option.option_id, player_id=am_player.id)
    assert str(getattr(regiment, "reserve_status", "") or "") == "strategic_reserves"
    assert regiment not in list(getattr(game.map, "units", []) or [])


def test_armoured_infantry_grand_strategist_requires_bearer_or_transport_on_battlefield():
    game, am_player, enemy_player, army, _enemy_army = _build_game()
    game.attacker_index = game.players.index(am_player)
    game.defender_index = game.players.index(enemy_player)
    officer = _officer("Embarked Commander")
    transport = _make_unit(
        "Chimera",
        keywords=["TRANSPORT", "VEHICLE"],
        wounds=11,
        transport="Transport Capacity: 12 Astra Militarum Infantry models",
    )
    regiment = _make_unit("Infantry Squad", keywords=["INFANTRY", "REGIMENT"], wounds=1)
    for unit in (officer, transport, regiment):
        army.add_unit(unit)
    _grand_strategist().apply_to_unit(officer)
    officer.embarked_in = transport
    transport.transport_passengers.append(officer)
    _place_unit(game, transport, 10.0, 10.0)
    _place_unit(game, regiment, 12.0, 10.0)
    game.rebuild_entity_registry()

    game.execute_redeploy_units_phase()
    assert _find_redeploy_request(game, ability_name="Grand Strategist") is not None

    while game.decision_queue.pop() is not None:
        pass
    game._redeploy_state = None
    transport.reserve_status = "strategic_reserves"
    game.execute_redeploy_units_phase()
    assert _find_redeploy_request(game, ability_name="Grand Strategist") is None


def test_armoured_infantry_grand_strategist_is_distinct_from_combined_arms_grand_strategist():
    _game, _am_player, _enemy_player, army, _enemy_army = _build_game(detachment_type="Combined Arms")
    officer = _officer("Combined Arms Commander")
    army.add_unit(officer)
    Enhancement(
        id="000008380004",
        name="Grand Strategist",
        faction_id="AM",
        detachment="Combined Arms",
        points=15,
        description="Officer model only. In your Command phase, the bearer can issue one additional Order.",
    ).apply_to_unit(officer)

    assert bool(officer.special_rules.get("enhancement_grand_strategist"))
    assert not bool(officer.special_rules.get("enhancement_armoured_infantry_grand_strategist"))
    assert officer.has_redeploy() == (False, 0, False)
