from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear


MARTIAL_HONOUR_TEXT = (
    "The first time a model in this model's unit makes a melee attack that destroys one or more enemy units, until "
    "the end of the battle, while this model's unit is not Battle-shocked, add 5 to this model's Objective Control "
    "characteristic."
)
RIGHTEOUS_ZEAL_TEXT = (
    "In your opponent's Shooting phase, each time an enemy unit has shot, if any models in this unit were destroyed "
    "as a result of those attacks, this unit can make a Righteous Zeal move. To do so, roll one D6 and add 2 to "
    "the result: models in this unit move a number of inches up to this result, but this unit must end that move as "
    "close as possible to the closest enemy unit (excluding AIRCRAFT). When doing so, those models can be moved "
    "within Engagement Range of that enemy unit. This unit cannot make a Righteous Zeal move while it is "
    "Battle-shocked or within Engagement Range of one or more enemy units, and can only make one Righteous Zeal move "
    "per phase."
)
ICON_OF_OBSTINACY_TEXT = (
    "Each time an attack targets this model's unit, if the Strength characteristic of that attack is greater than "
    "or equal to the Toughness characteristic of that unit, subtract 1 from the Wound roll."
)


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        model_count=1,
        wounds=4,
        toughness=4,
        objective_control=1,
        base_size="32mm",
    ):
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": str(int(toughness)),
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": str(int(objective_control)),
                "base_size": base_size,
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    model_count=1,
    wounds=4,
    toughness=4,
    objective_control=1,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            objective_control=objective_control,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army.with_detachment("Space Marines", "Test")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", control=PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    return game, sm_army, enemy_army


def _attach_leader(bodyguard: Unit, leader: Unit) -> None:
    leader.can_be_attached_to = [bodyguard.name]
    try:
        leader.attach_to_unit(bodyguard)
    except Exception:
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]
        for unit in (leader, bodyguard):
            invalidate_cache = getattr(unit, "_invalidate_ability_cache", None)
            if callable(invalidate_cache):
                invalidate_cache()
        bodyguard._parse_against_attack_characteristic_defensive_rules()


def _set_model_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _melee_profile():
    weapon = Wargear(
        {
            "name": "Test Blade",
            "type": "Melee",
            "range": "Melee",
            "A": "1",
            "BS_WS": "3+",
            "S": "6",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def _ranged_profile(*, strength: int):
    weapon = Wargear(
        {
            "name": f"Test Gun S{int(strength)}",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": str(int(strength)),
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )
    return weapon.profiles["default"]


def test_crusade_ancient_martial_honour_grants_only_the_ancient_plus_five_objective_control():
    game, sm_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Sword Brethren Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
    )
    ancient = _make_unit(
        "Crusade Ancient",
        abilities=[_ability("Martial Honour", MARTIAL_HONOUR_TEXT)],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy_one = _make_unit("Enemy One", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    enemy_two = _make_unit("Enemy Two", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(ancient)
    enemy_army.add_unit(enemy_one)
    enemy_army.add_unit(enemy_two)
    _attach_leader(bodyguard, ancient)

    leader_model = ancient.models[0]
    bodyguard_model = bodyguard.models[0]

    assert int(bodyguard.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 1
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0) == 1

    game._on_unit_destroyed_rules(
        unit=enemy_one,
        destroyed_by_unit=bodyguard,
        destroyed_by_model=bodyguard_model,
        destroyed_by_weapon_profile=_melee_profile(),
    )

    assert int(bodyguard.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 6
    assert int(bodyguard.get_effective_model_characteristic(bodyguard_model, "objective_control") or 0) == 1

    bodyguard.status_effects = [BattleShockEffect()]
    assert int(bodyguard.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 1

    bodyguard.status_effects = []
    assert int(bodyguard.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 6

    game._on_unit_destroyed_rules(
        unit=enemy_two,
        destroyed_by_unit=bodyguard,
        destroyed_by_model=bodyguard_model,
        destroyed_by_weapon_profile=_melee_profile(),
    )
    assert int(bodyguard.get_effective_model_characteristic(leader_model, "objective_control") or 0) == 6


def test_crusader_squad_righteous_zeal_uses_horde_move_rules_with_plus_two_distance():
    game, sm_army, enemy_army = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    crusader = _make_unit(
        "Crusader Squad",
        abilities=[_ability("Righteous Zeal", RIGHTEOUS_ZEAL_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
    )
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])
    sm_army.add_unit(crusader)
    enemy_army.add_unit(enemy)
    _set_model_location(crusader, 0.0, 0.0)
    _set_model_location(enemy, 12.0, 0.0)
    _register_units(game, crusader, enemy)

    assert crusader.has_horde_move()
    rule = crusader.get_horde_move_rule(game=game)
    assert rule is not None
    assert str(rule.get("source", "") or "") == "Righteous Zeal"
    assert int(rule.get("distance_bonus", 0) or 0) == 2
    assert bool(rule.get("requires_not_engaged", False)) is True
    assert bool(rule.get("use_once_per_phase", False)) is True

    assert crusader.can_horde_move(game=game, game_map=game.map) is True
    crusader.mark_horde_move_used(game)
    assert crusader.can_horde_move(game=game, game_map=game.map) is False

    game.phase = BattleRoundPhases.FIGHT_PHASE
    assert crusader.can_horde_move(game=game, game_map=game.map) is True

    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        assert game.roll_horde_move_distance(crusader) == 6


def test_darnath_lysander_icon_of_obstinacy_applies_when_strength_equals_or_exceeds_toughness_while_leading():
    game, sm_army, enemy_army = _build_game()
    bodyguard = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=2,
        toughness=4,
    )
    lysander = _make_unit(
        "Darnath Lysander",
        abilities=[_ability("Icon of Obstinacy", ICON_OF_OBSTINACY_TEXT)],
        keywords=["CHARACTER", "INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        toughness=4,
    )
    attacker = _make_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ENEMY"])

    sm_army.add_unit(bodyguard)
    sm_army.add_unit(lysander)
    enemy_army.add_unit(attacker)
    _attach_leader(bodyguard, lysander)
    _register_units(game, bodyguard, lysander, attacker)

    attacker_model = attacker.models[0]

    low_wound = _ranged_profile(strength=3)._wound_target_with_tracking(
        bodyguard,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    equal_wound = _ranged_profile(strength=4)._wound_target_with_tracking(
        bodyguard,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    high_wound = _ranged_profile(strength=5)._wound_target_with_tracking(
        bodyguard,
        attacker_model,
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    assert not any("Icon of Obstinacy" in str(mod) for mod in list(low_wound.get("modifiers", []) or []))
    assert any("Icon of Obstinacy" in str(mod) for mod in list(equal_wound.get("modifiers", []) or []))
    assert any("Icon of Obstinacy" in str(mod) for mod in list(high_wound.get("modifiers", []) or []))
