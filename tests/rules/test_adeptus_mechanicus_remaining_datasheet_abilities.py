import types
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        abilities=None,
        model_count=1,
        keywords=None,
        faction_keywords=None,
    ):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": f"{model_count} Test Model"}]
        self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_ability(name: str, description: str) -> dict:
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
    model_count=1,
    keywords=None,
    faction_keywords=None,
):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        abilities=abilities,
        model_count=model_count,
        keywords=keywords,
        faction_keywords=faction_keywords,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _build_game():
    army_adm = Army.with_detachment("Adeptus Mechanicus", detachment_type="Other")
    army_adm.faction_id = "ADM"
    army_enemy = Army.with_detachment("Enemy", detachment_type="Other")
    army_enemy.faction_id = "EN"

    adm_player = Player("AdMech", PlayerControl.REMOTE, army=army_adm)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=army_enemy)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[adm_player, enemy_player])
    game.current_player_index = 0
    return game, army_adm, army_enemy, adm_player, enemy_player


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def test_bomb_rack_parses_moved_across_variant():
    ability_text = (
        "Each time this model ends a Normal move, you can select one enemy unit it moved across during that move "
        "and roll six D6: for each 4+, that unit suffers 1 mortal wound."
    )
    unit = _make_unit(
        "Archaeopter Fusilave",
        abilities=[_make_ability("Bomb Rack", ability_text)],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    specs = unit.model_move_over_mortal_wounds_specs(model=unit.models[0])
    assert len(specs) == 1
    spec = specs[0]
    assert int(spec.get("dice", 0) or 0) == 6
    assert int(spec.get("threshold", 0) or 0) == 4
    assert int(spec.get("mortal_per_success", 0) or 0) == 1
    assert list(spec.get("move_types") or []) == ["move"]


def test_dynamic_efficiency_and_elevated_strider_reroll_desperate_escape_tests():
    dynamic_text = (
        "This unit is eligible to declare a charge in a turn in which it Advanced or Fell Back, and you can re-roll "
        "Desperate Escape tests taken for models in this unit."
    )
    elevated_text = (
        "This unit is eligible to shoot in a turn in which it Fell Back or Advanced, and you can re-roll Desperate "
        "Escape tests taken for models in this unit."
    )
    for ability_name, ability_text in (
        ("Dynamic Efficiency", dynamic_text),
        ("Elevated Strider", elevated_text),
    ):
        unit = _make_unit(
            f"Unit-{ability_name}",
            abilities=[_make_ability(ability_name, ability_text)],
            faction_keywords=["ADEPTUS MECHANICUS"],
        )
        assert bool(unit.special_rules.get("unit_reroll_desperate_escape_tests"))
        with patch("warhammer40k_ai.units.unit.get_roll", side_effect=[1, 6]):
            destroyed = unit.take_desperate_escape_test()
        assert destroyed == 0


def test_breaching_command_applies_full_hit_reroll_with_battleline():
    ability_text = (
        "Each time a model in this unit makes an attack, re-roll a Hit roll of 1. While this unit is within 6\" of "
        "one or more friendly Adeptus Mechanicus Battleline units, you can re-roll the Hit roll instead."
    )
    game, army_adm, army_enemy, _, _ = _build_game()
    attacker = _make_unit(
        "Kataphron Breachers",
        abilities=[_make_ability("Breaching Command", ability_text)],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit("Target", keywords=["INFANTRY"])
    army_adm.add_unit(attacker)
    army_enemy.add_unit(target)
    game.map.units = [attacker, target]
    attacker._within_friendly_adeptus_mechanicus_battleline = lambda **_kwargs: True

    modifiers = attacker.get_unit_hit_reroll_modifiers("ranged", target=target)
    assert bool(modifiers.get("reroll_hit_ones"))
    assert bool(modifiers.get("reroll_hit_full"))


def test_optimised_gait_applies_conditional_extra_bonus_for_advance_and_charge():
    ability_text = (
        "Add 1 to Advance and Charge rolls made for this unit. While this unit is within 6\" of one or more "
        "friendly Adeptus Mechanicus Battleline units, add 2 to Advance and Charge rolls made for this unit instead."
    )
    game, army_adm, _, _, _ = _build_game()
    unit = _make_unit(
        "Sicarian Ruststalkers",
        abilities=[_make_ability("Optimised Gait", ability_text)],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army_adm.add_unit(unit)
    game.map.units = [unit]
    unit._within_friendly_adeptus_mechanicus_battleline = lambda **_kwargs: True

    advance_total = sum(int(v or 0) for v, _ in list(unit._collect_advance_roll_modifiers() or []))
    charge_total = sum(int(v or 0) for v, _ in list(game._collect_charge_modifiers(unit) or []))
    assert advance_total == 2
    assert charge_total == 2


def test_line_breakers_applies_start_charge_bonus_and_engagement_only_model_count():
    ability_text = (
        "Each time this unit ends a Charge move, select one enemy unit within Engagement Range of it and roll one D6 "
        "for each model in this unit that is within Engagement Range of that enemy unit, adding 2 to the result if "
        "this unit started its Charge move within 6\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units. "
        "For each 4+, that enemy unit suffers 1 mortal wound."
    )
    game, army_adm, army_enemy, _, _ = _build_game()
    unit = _make_unit(
        "Serberys Sulphurhounds",
        abilities=[_make_ability("Line-breakers", ability_text)],
        model_count=2,
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Unit", model_count=1, faction_keywords=["ENEMY"])
    battleline = _make_unit(
        "Skitarii Rangers",
        model_count=1,
        keywords=["BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    army_adm.add_unit(unit)
    army_adm.add_unit(battleline)
    army_enemy.add_unit(enemy)
    game.map.units = [unit, battleline, enemy]

    unit.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    unit.models[1].set_location(8.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(0.6, 0.0, 0.0, 0.0)
    battleline.models[0].set_location(0.0, 1.0, 0.0, 0.0)
    unit.models[0].last_move_path = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
    unit.models[1].last_move_path = [(1.0, 0.0, 0.0), (8.0, 0.0, 0.0)]

    specs = list(unit.special_rules.get("charge_end_mortal_wounds", []) or [])
    spec = next(s for s in specs if str(s.get("kind", "") or "") == "per_model_4plus_1")
    assert bool(spec.get("engagement_only"))
    assert int(spec.get("start_charge_bonus", 0) or 0) == 2

    applied = {}

    def _apply(self, target, amount, game_map=None):
        applied["target"] = target
        applied["amount"] = applied.get("amount", 0) + int(amount or 0)
        return 0

    unit._apply_mortal_wounds_to_unit = types.MethodType(_apply, unit)
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2]):
        game.resolve_charge_end_mortal_wounds(unit, enemy, spec)

    assert applied.get("target") is enemy
    assert int(applied.get("amount", 0) or 0) == 1


def test_ride_the_thermals_queues_dual_mode_reactive_move_and_followup():
    ability_text = (
        "In your Shooting phase, after this unit has shot, if it is not within Engagement Range of one or more enemy "
        "units, it can do one of the following: - Make a Normal move of up to 6\". - Make a Normal move of up to 12\", "
        "provided every model in this unit ends that move wholly within 6\" of one or more friendly Adeptus Mechanicus "
        "Battleline units. In either case, if it does, until the end of the turn, this unit is not eligible to declare a charge."
    )
    game, army_adm, army_enemy, adm_player, _ = _build_game()
    unit = _make_unit(
        "Pteraxii Skystalkers",
        abilities=[_make_ability("Ride the Thermals", ability_text)],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    battleline = _make_unit(
        "Skitarii Rangers",
        keywords=["BATTLELINE"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    enemy = _make_unit("Enemy Unit", faction_keywords=["ENEMY"])
    army_adm.add_unit(unit)
    army_adm.add_unit(battleline)
    army_enemy.add_unit(enemy)
    game.map.units = [unit, battleline, enemy]
    unit.models[0].set_location(8.0, 0.0, 0.0, 0.0)
    battleline.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.rebuild_entity_registry()

    game._on_unit_shooting_resolved_tactical_acumen(attacker_unit=unit, hits_by_target={enemy: 1})

    req = game.decision_queue.peek()
    assert req is not None
    assert req.decision_type == DECISION_CONFIRM_YES_NO
    labels = [str(getattr(opt, "label", "") or "") for opt in list(req.options or [])]
    assert '6" Move' in labels
    assert '12" Battleline Move' in labels
    assert "Skip" in labels

    battleline_opt = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("post_shoot_no_charge_mode", "") or "") == "battleline_6"
    )
    resolve_decision_command(game, req, battleline_opt.option_id, player_id=adm_player.id)

    move_req = game.decision_queue.peek()
    assert move_req is not None
    assert move_req.decision_type == DECISION_MOVE_UNIT
    ctx = dict(getattr(move_req, "context", {}) or {})
    assert str(ctx.get("tactica_obliqua_mode", "") or "") == "battleline_6"
