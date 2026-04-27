from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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
