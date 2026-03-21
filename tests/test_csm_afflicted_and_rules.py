from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.nurgles_gift import NurglesGiftManager, PLAGUE_SKULLSQUIRM
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


INFUSED_TEXT = (
    "In your Shooting phase, each time this unit is selected to shoot, after this unit has shot, "
    "select one enemy unit hit by one or more of those attacks. Until the start of your next turn, "
    "that enemy unit is Afflicted."
)

HAMADRYA_TEXT = (
    "Once per battle round, when an enemy unit ends a Normal, Advance or Fall Back move within 9\" of this model's unit, "
    "if this model's unit is not within Engagement Range of one or more enemy units, it can make a Normal move of up to D3+3\"."
)

MALIGN_COVER_TEXT = (
    "Each time a ranged attack is allocated to a model, if that model is not fully visible to every model in the attacking "
    "unit because of this FORTIFICATION, that model has the Benefit of Cover against that attack."
)


def _make_unit(name, army, *, ability_name=None, ability_text=None, keywords=None, faction_keywords=None):
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
        unit.possible_abilities = [
            Ability(ability_name or "Ability", unit.faction, ability_text, ""),
        ]
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
    army_a = Army("Army A", detachment_type="Other")
    army_a.faction_id = "CSM"
    army_b = Army("Army B", detachment_type="Other")
    army_b.faction_id = "ENEMY"

    player_a = Player("Player A", PlayerControl.LOCAL, army=army_a)
    player_b = Player("Player B", PlayerControl.LOCAL, army=army_b)

    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield, players=[player_a, player_b])
    game.current_player_index = 0
    return game, player_a, player_b, army_a, army_b


def test_csm_infused_with_blessings_marks_afflicted_and_cleans_up():
    game, player_a, _player_b, army_a, army_b = _build_game()

    attacker = _make_unit(
        "Plague Marines",
        army_a,
        ability_name="Infused with the Blessings of Nurgle",
        ability_text=INFUSED_TEXT,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit("Enemy Target", army_b, keywords=["INFANTRY"])

    attacker.models = [_make_model("Attacker", attacker, 0.0, 0.0)]
    target.models = [_make_model("Target", target, 8.0, 0.0)]

    army_a.units = [attacker]
    army_b.units = [target]
    game.map.units = [attacker, target]
    game.is_shooting_phase = lambda: True

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        hits_by_target={target: 1},
    )

    pending = game.decision_queue.list()
    afflicted_reqs = [
        req
        for req in pending
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "")) == "post_shoot_afflicted"
    ]
    assert len(afflicted_reqs) == 1

    req = afflicted_reqs[0]
    target_option = None
    for opt in list(req.options or []):
        if str((opt.payload or {}).get("target_unit_id", "")) == str(get_entity_id(target) or ""):
            target_option = opt
            break
    assert target_option is not None
    resolve_decision_command(game, req, target_option.option_id, player_id=player_a.id)

    sr = dict(getattr(target, "special_rules", {}) or {})
    assert bool(sr.get("post_shoot_afflicted_active", False)) is True
    assert str(sr.get("post_shoot_afflicted_owner", "")) == str(player_a.id)

    game._on_phase_start_post_shoot_afflicted_cleanup(
        player=player_a,
        phase=SimpleNamespace(name="COMMAND_PHASE"),
    )

    sr_after = dict(getattr(target, "special_rules", {}) or {})
    assert bool(sr_after.get("post_shoot_afflicted_active", False)) is False


def test_csm_infused_afflicted_is_visible_to_nurgles_gift_manager_when_active():
    game, player_a, _player_b, army_a, army_b = _build_game()

    army_a.nurgles_gift = NurglesGiftManager(army_a)
    army_a.nurgles_gift.active_plague_key = PLAGUE_SKULLSQUIRM.key

    source = _make_unit("Plague Marines", army_a, keywords=["INFANTRY"])
    target = _make_unit("Enemy Target", army_b, keywords=["INFANTRY"])
    source.models = [_make_model("Source", source, 0.0, 0.0)]
    target.models = [_make_model("Target", target, 20.0, 0.0)]
    army_a.units = [source]
    army_b.units = [target]

    target.special_rules = {
        "post_shoot_afflicted_active": True,
        "post_shoot_afflicted_owner": str(player_a.id),
        "post_shoot_afflicted_turn": 1,
        "post_shoot_afflicted_source": "Infused with the Blessings of Nurgle",
    }

    plague = NurglesGiftManager.get_afflicted_plague_for_unit(target, game=game, game_map=None)
    assert plague is not None
    assert plague.key == PLAGUE_SKULLSQUIRM.key


def test_csm_infused_with_blessings_has_no_effect_when_disabled():
    game, _player_a, _player_b, army_a, army_b = _build_game()

    attacker = _make_unit(
        "Plague Marines",
        army_a,
        ability_name="Infused with the Blessings of Nurgle",
        ability_text=INFUSED_TEXT,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    target = _make_unit("Enemy Target", army_b, keywords=["INFANTRY"])

    attacker.models = [_make_model("Attacker", attacker, 0.0, 0.0)]
    target.models = [_make_model("Target", target, 8.0, 0.0)]
    attacker.special_rules["infused_blessings_of_nurgle_disabled"] = True

    army_a.units = [attacker]
    army_b.units = [target]
    game.map.units = [attacker, target]
    game.is_shooting_phase = lambda: True

    assert attacker.unit_post_shoot_afflicted_specs() == []

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        hits_by_target={target: 1},
    )

    afflicted_reqs = [
        req
        for req in list(game.decision_queue.list() or [])
        if req.decision_type == DECISION_CHOOSE_QUARRY
        and str((req.context or {}).get("ability", "")) == "post_shoot_afflicted"
    ]
    assert afflicted_reqs == []


def test_csm_hamadrya_knowledge_parses_once_per_battle_round_reactive_move():
    army = Army("CSM", detachment_type="Other")
    unit = _make_unit(
        "Huron Blackheart",
        army,
        ability_name="Hamadrya's Knowledge (Psychic)",
        ability_text=HAMADRYA_TEXT,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    rule = unit.get_loping_speed_rule()
    assert rule is not None
    assert int(rule.get("range", 0) or 0) == 9
    assert str(rule.get("distance_roll", "")) == "D3+3"
    assert bool(rule.get("once_per_battle", False)) is True


def test_csm_malign_cover_fortification_rule_parses():
    army = Army("CSM", detachment_type="Other")
    unit = _make_unit(
        "Noctilith Crown",
        army,
        ability_name="Malign Cover",
        ability_text=MALIGN_COVER_TEXT,
        keywords=["FORTIFICATION"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    rule = unit.get_fortification_cover_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "")) == "Malign Cover"
