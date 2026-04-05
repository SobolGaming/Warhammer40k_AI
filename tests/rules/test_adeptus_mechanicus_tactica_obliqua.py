from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


TACTICA_OBLIQUA_TEXT = (
    "Once per turn, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this unit, "
    "if this unit is not within Engagement Range of one or more enemy units, it can do one of the following: "
    "- Make a Normal move of up to D6\". "
    "- Make a Normal move of up to 6\", provided every model in this unit ends that move wholly within 6\" "
    "of one or more friendly Adeptus Mechanicus Battleline units."
)


def _make_unit(name, army, *, ability_text=None, keywords=None, faction_keywords=None):
    unit = Unit.__new__(Unit)
    unit.name = name
    unit._id = name
    unit.parent_army = army
    unit.faction = getattr(army, "faction_id", "")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models = []
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.possible_abilities = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = SimpleNamespace()
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit.embarked_in = None
    unit._ability_cache = {}
    if ability_text:
        unit.possible_abilities = [Ability("Tactica Obliqua", unit.faction, ability_text, "")]
    return unit


def _make_model(name, unit, x, y):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


def _build_game():
    army_move = Army("Moving Army", detachment_type="Other")
    army_move.faction_id = "EN"
    army_react = Army("Adeptus Mechanicus", detachment_type="Other")
    army_react.faction_id = "ADM"

    moving_player = Player("Mover", PlayerControl.REMOTE, army=army_move)
    reacting_player = Player("Reactor", PlayerControl.REMOTE, army=army_react)

    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield, players=[moving_player, reacting_player])
    game.current_player_index = 0
    return game, moving_player, reacting_player, army_move, army_react


def _queue_tactica_trigger(game, moving_unit):
    game.event_system.publish(
        "unit_move_ended",
        unit=moving_unit,
        action="move",
    )
    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CONFIRM_YES_NO
    return request


def _select_option_by_payload(request, *, key, value):
    for option in list(request.options or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if payload.get(key) == value:
            return option
    return None


def test_tactica_obliqua_rule_parses_battleline_move_option():
    game, _moving_player, _reacting_player, _army_move, army_react = _build_game()
    reacting_unit = _make_unit(
        "Serberys Raiders",
        army_react,
        ability_text=TACTICA_OBLIQUA_TEXT,
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    rule = reacting_unit.get_loping_speed_rule()
    assert rule is not None
    assert int(rule.get("range", 0) or 0) == 9
    assert str(rule.get("distance_roll", "") or "").upper() == "D6"
    assert int(rule.get("battleline_wholly_within_max_distance", 0) or 0) == 6
    assert int(rule.get("battleline_wholly_within_range", 0) or 0) == 6


def test_tactica_obliqua_queues_three_way_choice_in_remote_mode():
    game, _moving_player, reacting_player, army_move, army_react = _build_game()

    moving_unit = _make_unit("Enemy Movers", army_move, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    reacting_unit = _make_unit(
        "Serberys Raiders",
        army_react,
        ability_text=TACTICA_OBLIQUA_TEXT,
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    battleline = _make_unit(
        "Skitarii Rangers",
        army_react,
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army_move.units = [moving_unit]
    army_react.units = [reacting_unit, battleline]

    moving_unit.models = [_make_model("Enemy Model", moving_unit, 0.0, 0.0)]
    reacting_unit.models = [_make_model("Raider", reacting_unit, 8.0, 0.0)]
    battleline.models = [_make_model("Ranger", battleline, 0.0, 0.0)]

    game.map.units = [moving_unit, reacting_unit, battleline]
    game.rebuild_entity_registry()

    request = _queue_tactica_trigger(game, moving_unit)
    assert request.player_id == reacting_player.id
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("reactive_move_kind", "") or "") == "tactica_obliqua"

    labels = [str(getattr(opt, "label", "") or "") for opt in list(request.options or [])]
    assert "D6 Move" in labels
    assert "6\" Battleline Move" in labels
    assert "Skip" in labels


def test_tactica_obliqua_battleline_mode_rejects_invalid_end_position():
    game, _moving_player, reacting_player, army_move, army_react = _build_game()

    moving_unit = _make_unit("Enemy Movers", army_move, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    reacting_unit = _make_unit(
        "Serberys Raiders",
        army_react,
        ability_text=TACTICA_OBLIQUA_TEXT,
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    battleline = _make_unit(
        "Skitarii Rangers",
        army_react,
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army_move.units = [moving_unit]
    army_react.units = [reacting_unit, battleline]

    moving_unit.models = [_make_model("Enemy Model", moving_unit, 0.0, 0.0)]
    reacting_model = _make_model("Raider", reacting_unit, 8.0, 0.0)
    reacting_unit.models = [reacting_model]
    battleline.models = [_make_model("Ranger", battleline, 0.0, 0.0)]

    game.map.units = [moving_unit, reacting_unit, battleline]
    game.rebuild_entity_registry()

    confirm_request = _queue_tactica_trigger(game, moving_unit)
    battleline_option = _select_option_by_payload(
        confirm_request,
        key="tactica_obliqua_mode",
        value="battleline_6",
    )
    assert battleline_option is not None
    resolve_decision_command(
        game,
        confirm_request,
        battleline_option.option_id,
        player_id=reacting_player.id,
    )

    move_request = game.decision_queue.peek()
    assert move_request is not None
    assert move_request.decision_type == DECISION_MOVE_UNIT
    confirm_move = _select_option_by_payload(move_request, key="action", value="confirm")
    assert confirm_move is not None
    result = resolve_decision_command(
        game,
        move_request,
        confirm_move.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(reacting_model),
                    "position": [10.0, 0.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
        player_id=reacting_player.id,
    )
    assert bool(getattr(result, "ok", False)) is False


def test_tactica_obliqua_battleline_mode_accepts_valid_end_position_and_marks_used():
    game, _moving_player, reacting_player, army_move, army_react = _build_game()

    moving_unit = _make_unit("Enemy Movers", army_move, keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    reacting_unit = _make_unit(
        "Serberys Raiders",
        army_react,
        ability_text=TACTICA_OBLIQUA_TEXT,
        keywords=["MOUNTED"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    battleline = _make_unit(
        "Skitarii Rangers",
        army_react,
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army_move.units = [moving_unit]
    army_react.units = [reacting_unit, battleline]

    moving_unit.models = [_make_model("Enemy Model", moving_unit, 0.0, 0.0)]
    reacting_model = _make_model("Raider", reacting_unit, 8.0, 0.0)
    reacting_unit.models = [reacting_model]
    battleline.models = [_make_model("Ranger", battleline, 0.0, 0.0)]

    game.map.units = [moving_unit, reacting_unit, battleline]
    game.rebuild_entity_registry()

    confirm_request = _queue_tactica_trigger(game, moving_unit)
    battleline_option = _select_option_by_payload(
        confirm_request,
        key="tactica_obliqua_mode",
        value="battleline_6",
    )
    assert battleline_option is not None
    resolve_decision_command(
        game,
        confirm_request,
        battleline_option.option_id,
        player_id=reacting_player.id,
    )

    move_request = game.decision_queue.peek()
    assert move_request is not None
    assert move_request.decision_type == DECISION_MOVE_UNIT
    confirm_move = _select_option_by_payload(move_request, key="action", value="confirm")
    assert confirm_move is not None
    result = resolve_decision_command(
        game,
        move_request,
        confirm_move.option_id,
        result_payload={
            "model_positions": [
                {
                    "model_id": get_entity_id(reacting_model),
                    "position": [4.0, 0.0, 0.0],
                    "facing": 0.0,
                }
            ]
        },
        player_id=reacting_player.id,
    )
    assert bool(getattr(result, "ok", False))
    assert reacting_unit.loping_speed_used_this_turn(game)
