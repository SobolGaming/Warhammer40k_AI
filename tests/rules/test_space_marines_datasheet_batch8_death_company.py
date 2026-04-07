from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


FORLORN_HERO_TEXT = (
    "While this model is leading a unit, unless that unit starts the battle embarked within a Transport, "
    "models in that unit have the Scouts 6\" ability."
)
DRIVEN_BY_FURY_TEXT = (
    "In your opponent's Shooting phase, each time an enemy unit has shot, if this model was hit by one or more of those attacks, "
    "it can make a Driven by Fury move. To do so, roll one D6 and add 2 to the roll: this model moves a number of inches up to "
    "the result, but must finish as close as possible to the closest enemy unit (excluding AIRCRAFT). When doing so, this model can "
    "be moved within Engagement Range of that enemy unit. A model cannot make a Driven by Fury move while it is Battle-shocked or "
    "within Engagement Range of one or more enemy units, and can only make one Driven by Fury move per phase."
)
AN_HONOURABLE_DEATH_IN_COMBAT_TEXT = (
    "Each time a model in this unit makes an attack, that attack has the [SUSTAINED HITS 1] ability if this unit is below its "
    "Starting Strength, or the [SUSTAINED HITS 2] ability if this unit is Below Half-strength."
)
VISIONS_OF_HERESY_TEXT = (
    "Once per turn, you can target this unit with the Fire Overwatch or the Heroic Intervention Stratagem for 0CP. "
    "While resolving that Stratagem, each time a model in this unit makes a ranged attack you can re-roll the Hit roll, "
    "or you can re-roll the Charge roll made for this unit (whichever applies)."
)


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        abilities=None,
        keywords=None,
        faction_keywords=None,
        attached_to_names=None,
        model_count: int = 1,
        wounds: int = 4,
        toughness: int = 4,
        objective_control: int = 1,
        base_size: str = "32mm",
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": "Space Marines"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} model(s)", "cost": 100}]
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
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = list(attached_to_names or [])
        self.attached_to_names = list(attached_to_names or [])


def _ability(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "type": "Datasheet",
        "parameter": "",
    }


def _make_unit(
    name: str,
    *,
    abilities=None,
    keywords=None,
    faction_keywords=None,
    attached_to_names=None,
    model_count: int = 1,
    wounds: int = 4,
    toughness: int = 4,
    objective_control: int = 1,
    base_size: str = "32mm",
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            abilities=abilities,
            keywords=keywords,
            faction_keywords=faction_keywords,
            attached_to_names=attached_to_names,
            model_count=model_count,
            wounds=wounds,
            toughness=toughness,
            objective_control=objective_control,
            base_size=base_size,
        ),
        quantity=int(model_count),
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    game.add_player(enemy_player)
    game.add_player(sm_player)
    game.current_player_index = 0
    game.turn = 1
    return game, enemy_player, sm_player, enemy_army, sm_army


def _set_unit_location(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _first_option(request, predicate):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if predicate(payload):
            return option
    return None


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
    apply_scouts = getattr(leader, "_apply_leading_bodyguard_scouts", None)
    if callable(apply_scouts):
        apply_scouts(bodyguard)


def _make_ranged_weapon() -> Wargear:
    return Wargear(
        {
            "name": "Bolt Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        }
    )


def test_death_company_captain_forlorn_hero_requires_bodyguard_not_embarked_for_scouts():
    bodyguard = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    leader = _make_unit(
        "Death Company Captain",
        abilities=[_ability("Forlorn Hero", FORLORN_HERO_TEXT)],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        attached_to_names=["Assault Intercessors"],
    )
    _attach_leader(bodyguard, leader)

    has_scout, scout_distance = bodyguard.has_scout()
    assert has_scout is True
    assert float(scout_distance) == 6.0

    embarked_bodyguard = _make_unit(
        "Assault Intercessors",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
    )
    embarked_bodyguard.embarked_in = object()
    embarked_leader = _make_unit(
        "Death Company Captain",
        abilities=[_ability("Forlorn Hero", FORLORN_HERO_TEXT)],
        keywords=["CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        attached_to_names=["Assault Intercessors"],
    )
    _attach_leader(embarked_bodyguard, embarked_leader)

    has_scout, scout_distance = embarked_bodyguard.has_scout()
    assert has_scout is False
    assert float(scout_distance) == 0.0


def test_death_company_dreadnought_driven_by_fury_triggers_horde_move_on_hits():
    game, _enemy_player, sm_player, enemy_army, sm_army = _build_game()
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=2,
    )
    dreadnought = _make_unit(
        "Death Company Dreadnought",
        abilities=[_ability("Driven by Fury", DRIVEN_BY_FURY_TEXT)],
        keywords=["VEHICLE", "WALKER"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=8,
        toughness=10,
        base_size="60mm",
    )

    enemy_army.add_unit(attacker)
    sm_army.add_unit(dreadnought)
    _set_unit_location(attacker, 0.0, 0.0)
    _set_unit_location(dreadnought, 10.0, 0.0)
    _register_units(game, attacker, dreadnought)

    rule = dreadnought.get_horde_move_rule(game=game)
    assert rule is not None
    assert str(rule.get("source", "") or "") == "Driven by Fury"
    assert int(rule.get("distance_bonus", 0) or 0) == 2
    assert bool(rule.get("requires_not_engaged", False)) is True
    assert bool(rule.get("use_once_per_phase", False)) is True

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[dreadnought])
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=4):
        game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={dreadnought: 1})

    confirm_request = next(
        request
        for request in list(game.decision_queue.list() or [])
        if request.decision_type == DECISION_CONFIRM_YES_NO
        and str((request.context or {}).get("reactive_move_kind", "")) == "horde_move"
    )
    assert str(confirm_request.player_id) == str(sm_player.id)
    yes_option = _first_option(confirm_request, lambda payload: bool(payload.get("choice", False)))
    assert yes_option is not None

    resolve_decision_command(game, confirm_request, yes_option.option_id, player_id=sm_player.id)

    move_request = next(
        request
        for request in list(game.decision_queue.list() or [])
        if request.decision_type == DECISION_MOVE_UNIT
        and str((request.context or {}).get("movement_type", "")) == "horde_move"
    )
    confirm_move = _first_option(move_request, lambda payload: str(payload.get("action", "")) == "confirm")
    assert confirm_move is not None

    model_positions = []
    for model in list(dreadnought.models or []):
        x, y, z, facing = model.get_location()
        model_positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(x), float(y), float(z)],
                "facing": float(facing),
            }
        )
    resolve_decision_command(
        game,
        move_request,
        confirm_move.option_id,
        player_id=sm_player.id,
        result_payload={"model_positions": model_positions},
    )

    assert dreadnought.horde_move_used_this_phase(game)


def test_death_company_marines_an_honourable_death_in_combat_scales_for_all_attacks():
    unit = _make_unit(
        "Death Company Marines",
        abilities=[_ability("An Honourable Death in Combat", AN_HONOURABLE_DEATH_IN_COMBAT_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=5,
        wounds=2,
    )
    target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
        wounds=2,
    )

    full_strength = unit.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=unit.models[0],
    )
    assert int(full_strength.get("sustained_hits_value", 0) or 0) == 0

    unit.models.pop()
    below_starting = unit.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=unit.models[0],
    )
    assert int(below_starting.get("sustained_hits_value", 0) or 0) == 1

    unit.models.pop()
    unit.models.pop()
    below_half = unit.get_attack_keyword_bonuses(
        target=target,
        attack_type="ranged",
        model=unit.models[0],
    )
    assert int(below_half.get("sustained_hits_value", 0) or 0) == 2


def test_death_company_marines_with_bolt_rifles_visions_of_heresy_zero_cp_overwatch_and_hit_reroll():
    game, _enemy_player, sm_player, _enemy_army, sm_army = _build_game()
    shooter = _make_unit(
        "Death Company Marines with Bolt Rifles",
        abilities=[_ability("Visions of Heresy", VISIONS_OF_HERESY_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=1,
        wounds=2,
    )
    target = _make_unit(
        "Enemy Unit",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
        wounds=2,
    )
    sm_army.add_unit(shooter)
    weapon = _make_ranged_weapon()
    shooter.models[0].wargear = [weapon]

    sm_player.set_next_optional_decision("VISIONS_OF_HERESY_STRATAGEM_DISCOUNT", True)
    applied = sm_player.apply_stratagem_cp_cost(SimpleNamespace(name="Fire Overwatch", cp_cost=1), target_unit=shooter)

    assert int(applied.get("cost", -1)) == 0
    assert bool(applied.get("visions_of_heresy_use", False))
    assert shooter.visions_of_heresy_used_this_turn(game)

    shooter.activate_visions_of_heresy_overwatch_hit_reroll(
        game,
        source=str(applied.get("visions_of_heresy_source", "") or ""),
        stratagem_name="Fire Overwatch",
    )
    shooter._overwatch_sixes_only = True
    shooter._overwatch_hit_threshold = 6
    profile = weapon.profiles["default"]

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 6]):
        hit_result = profile._hit_target_with_tracking(target, shooter.models[0], {})

    assert bool(hit_result.get("hit", False)) is True
    assert int(hit_result.get("reroll", 0) or 0) == 6
    assert "Visions of Heresy: re-roll Hit roll" in list(hit_result.get("special_effects", []) or [])

    shooter.clear_visions_of_heresy_overwatch_hit_reroll()
    del shooter._overwatch_sixes_only
    del shooter._overwatch_hit_threshold


def test_death_company_marines_with_bolt_rifles_visions_of_heresy_heroic_intervention_activates_charge_reroll():
    game, enemy_player, sm_player, enemy_army, sm_army = _build_game()
    game.phase = BattleRoundPhases.CHARGE_PHASE

    reacting_unit = _make_unit(
        "Death Company Marines with Bolt Rifles",
        abilities=[_ability("Visions of Heresy", VISIONS_OF_HERESY_TEXT)],
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
        model_count=1,
        wounds=2,
    )
    enemy = _make_unit(
        "Enemy Chargers",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        model_count=1,
        wounds=2,
    )
    sm_army.add_unit(reacting_unit)
    enemy_army.add_unit(enemy)
    _set_unit_location(reacting_unit, 0.0, 0.0)
    _set_unit_location(enemy, 5.0, 0.0)
    _register_units(game, reacting_unit, enemy)

    sm_player.command_points = 1
    reacting_unit.can_declare_charge_against = lambda target, current_game, out_of_turn=False: True
    sm_player.set_next_optional_decision("VISIONS_OF_HERESY_STRATAGEM_DISCOUNT", True)

    observed = {}

    def _fake_attempt_charge(charger, target, out_of_turn=False, count_as_charged=False):
        observed["charger_id"] = str(get_entity_id(charger) or "")
        observed["charge_reroll_active"] = bool(charger.can_reroll_charge_roll(game=game, game_map=game.map))
        return True

    game.current_player_index = 0
    assert enemy_player is game.get_current_player()

    with patch.object(game, "attempt_charge", side_effect=_fake_attempt_charge):
        assert sm_player.stratagems.use(
            "Heroic Intervention",
            enemy_unit=enemy,
            unit=reacting_unit,
            candidates=[reacting_unit],
            phase_name="Charge phase",
        )

    assert observed.get("charger_id") == str(get_entity_id(reacting_unit) or "")
    assert bool(observed.get("charge_reroll_active", False)) is True
    assert reacting_unit.visions_of_heresy_used_this_turn(game)
    assert "visions_of_heresy_heroic_intervention_charge_reroll_active" not in reacting_unit.special_rules
