from types import SimpleNamespace

from warhammer40k_ai.engine.decision_handlers.abilities import _apply_choose_quarry, _validate_choose_quarry
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.decisions import DecisionResult
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.rules.voice_of_command import ORDER_MOVE, ORDER_ON_MY_SIGNAL
from warhammer40k_ai.units.unit import Unit
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
        self.transport = ""
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
) -> Unit:
    unit = Unit(
        _Datasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            wounds=wounds,
            move=move,
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


def _find_quarry_request(game: Game, *, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == ability:
            return request
    return None


def _option_with_selected_units(request, selected_units):
    selected_ids = [str(get_entity_id(unit) or "") for unit in selected_units]
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if list(payload.get("selected_unit_ids", []) or []) == selected_ids:
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
