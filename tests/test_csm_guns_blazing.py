from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_DECLARE_SHOTS
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.utility.model_base import Base, BaseType


GUNS_BLAZING_TEXT = (
    "Once per turn, in your opponent's Shooting phase, when an enemy unit makes a ranged attack that targets "
    "a friendly HERETIC ASTARTES unit within 3\" of this model, after that enemy unit has shot, this model can "
    "shoot as if it were your Shooting phase, but it must target only that enemy unit when doing so, and can "
    "only do so if that enemy unit is an eligible target."
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
        unit.possible_abilities = [
            Ability("Guns Blazing", unit.faction, ability_text, ""),
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


def _build_game(*, reacting_control=PlayerControl.REMOTE):
    army_attack = Army("Attack Army", detachment_type="Other")
    army_attack.faction_id = "ATK"
    army_react = Army("React Army", detachment_type="Other")
    army_react.faction_id = "CSM"

    attacking_player = Player("Attacker", PlayerControl.LOCAL, army=army_attack)
    reacting_player = Player("Reactor", reacting_control, army=army_react)

    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    game = Game(battlefield, players=[attacking_player, reacting_player])
    game.current_player_index = 0
    return game, attacking_player, reacting_player, army_attack, army_react


def test_csm_guns_blazing_queues_out_of_phase_shooting_decision():
    game, _attacker_player, _reacting_player, army_attack, army_react = _build_game()

    attacker = _make_unit("Enemy Shooters", army_attack, keywords=["INFANTRY"])
    friendly_target = _make_unit(
        "Legionaries",
        army_react,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    cypher = _make_unit(
        "Cypher",
        army_react,
        ability_text=GUNS_BLAZING_TEXT,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    attacker.models = [_make_model("Enemy Model", attacker, 0.0, 0.0)]
    friendly_target.models = [_make_model("Legionary", friendly_target, 5.0, 0.0)]
    cypher.models = [_make_model("Cypher Model", cypher, 7.0, 0.0)]

    army_attack.units = [attacker]
    army_react.units = [friendly_target, cypher]
    game.map.units = [attacker, friendly_target, cypher]

    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[friendly_target],
    )
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        hits_by_target={friendly_target: 1},
    )

    pending = game.decision_queue.list()
    assert len(pending) == 1
    req = pending[0]
    assert req.decision_type == DECISION_DECLARE_SHOTS
    assert bool((req.context or {}).get("guns_blazing_flow", False)) is True
    assert str((req.context or {}).get("force_target_unit_id", "")) == str(get_entity_id(attacker) or "")


def test_csm_guns_blazing_once_per_turn_gate_blocks_repeat_trigger():
    game, _attacker_player, _reacting_player, army_attack, army_react = _build_game()

    attacker = _make_unit("Enemy Shooters", army_attack, keywords=["INFANTRY"])
    friendly_target = _make_unit(
        "Legionaries",
        army_react,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )
    cypher = _make_unit(
        "Cypher",
        army_react,
        ability_text=GUNS_BLAZING_TEXT,
        keywords=["INFANTRY", "HERETIC ASTARTES"],
        faction_keywords=["HERETIC ASTARTES"],
    )

    attacker.models = [_make_model("Enemy Model", attacker, 0.0, 0.0)]
    friendly_target.models = [_make_model("Legionary", friendly_target, 5.0, 0.0)]
    cypher.models = [_make_model("Cypher Model", cypher, 7.0, 0.0)]

    army_attack.units = [attacker]
    army_react.units = [friendly_target, cypher]
    game.map.units = [attacker, friendly_target, cypher]

    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    cypher.mark_guns_blazing_used(game)

    game.event_system.publish(
        "shooting_targets_selected",
        attacking_unit=attacker,
        target_units=[friendly_target],
    )
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=attacker,
        hits_by_target={friendly_target: 1},
    )

    pending = game.decision_queue.list()
    assert pending == []
