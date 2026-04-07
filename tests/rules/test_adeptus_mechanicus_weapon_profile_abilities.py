from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(self, name, *, abilities=None, keywords=None, faction_keywords=None):
        self.id = ""
        self.name = name
        self.faction_data = {"name": "Adeptus Mechanicus"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
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


def _make_unit(name, *, keywords=None, faction_keywords=None, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(
        name,
        keywords=keywords,
        faction_keywords=faction_keywords,
        abilities=abilities,
    )
    unit = Unit(datasheet)
    unit.deployed = True
    return unit


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    army_adm = Army.with_detachment("Adeptus Mechanicus", "Other")
    army_adm.faction_id = "ADM"
    army_enemy = Army.with_detachment("Enemy", "Other")
    army_enemy.faction_id = "EN"
    player_adm = Player("P1", control=PlayerControl.LOCAL, army=army_adm)
    player_enemy = Player("P2", control=PlayerControl.REMOTE, army=army_enemy)
    game.add_player(player_adm)
    game.add_player(player_enemy)
    return game, army_adm, army_enemy


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


def _make_profile(weapon_name: str):
    from warhammer40k_ai.units.wargear import Wargear

    data = {
        "name": weapon_name,
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
        "type": "Ranged",
    }
    return Wargear(data).profiles["default"]


def test_blistering_salvoes_applies_weapon_specific_hit_bonus():
    ability = _make_ability(
        "Blistering Salvoes",
        "Each time this model makes an attack with a belleros energy cannon that targets an INFANTRY unit, add 1 to the Hit roll.",
    )
    game, army_adm, army_enemy = _build_game()
    attacker = _make_unit(
        "Skorpius Disintegrator",
        abilities=[ability],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"])
    army_adm.add_unit(attacker)
    army_enemy.add_unit(target)

    profile = _make_profile("belleros energy cannon")
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
        result = profile._hit_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )

    assert bool(result.get("hit"))
    assert int(result.get("final_needed", 0) or 0) == 2
    assert any("Blistering Salvoes" in str(m or "") for m in list(result.get("modifiers", []) or []))


def test_achillan_eye_applies_weapon_specific_full_wound_reroll():
    ability = _make_ability(
        "Achillan Eye",
        "Each time this model makes an attack with a radium jezzail that targets an INFANTRY unit, you can re-roll the Wound roll.",
    )
    game, army_adm, army_enemy = _build_game()
    attacker = _make_unit(
        "Sydonian Skatros",
        abilities=[ability],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit("Enemy Infantry", keywords=["INFANTRY"])
    army_adm.add_unit(attacker)
    army_enemy.add_unit(target)

    called = {}

    def _provider(**kwargs):
        called["reason"] = kwargs.get("reason")
        return True

    game.map.roll_reroll_provider = _provider

    profile = _make_profile("radium jezzail")
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 6]):
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )

    assert int(result.get("roll", 0) or 0) == 6
    assert "Achillan Eye" in str(called.get("reason", "") or "")


def test_searing_conflagration_reroll_ones_within_objective_range():
    ability = _make_ability(
        "Searing Conflagration",
        "Each time a model in this unit makes an attack with a phosphor torch that targets an enemy unit within range of an objective marker, re-roll a Wound roll of 1.",
    )
    game, army_adm, army_enemy = _build_game()
    attacker = _make_unit(
        "Pteraxii Sterylizors",
        abilities=[ability],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    army_adm.add_unit(attacker)
    army_enemy.add_unit(target)
    attacker._target_within_objective_range = lambda _target, _game_map=None: True
    attacker._within_friendly_adeptus_mechanicus_battleline = lambda **_kwargs: False

    called = {}

    def _provider(**kwargs):
        called["reason"] = kwargs.get("reason")
        return True

    game.map.roll_reroll_provider = _provider

    profile = _make_profile("phosphor torch")
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[1, 6]):
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )

    assert int(result.get("roll", 0) or 0) == 6
    assert int(result.get("reroll_of_one", 0) or 0) == 1


def test_searing_conflagration_applies_full_reroll_with_battleline():
    ability = _make_ability(
        "Searing Conflagration",
        "Each time a model in this unit makes an attack with a phosphor torch that targets an enemy unit within range of an objective marker, re-roll a Wound roll of 1. If this unit is also within 6\" of one or more friendly ADEPTUS MECHANICUS BATTLELINE units, each time such an attack targets such a unit, you can re-roll the Wound roll instead.",
    )
    game, army_adm, army_enemy = _build_game()
    attacker = _make_unit(
        "Pteraxii Sterylizors",
        abilities=[ability],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    target = _make_unit("Enemy Unit", keywords=["INFANTRY"])
    army_adm.add_unit(attacker)
    army_enemy.add_unit(target)
    attacker._target_within_objective_range = lambda _target, _game_map=None: True
    attacker._within_friendly_adeptus_mechanicus_battleline = lambda **_kwargs: True

    called = {}

    def _provider(**kwargs):
        called["reason"] = kwargs.get("reason")
        return True

    game.map.roll_reroll_provider = _provider

    profile = _make_profile("phosphor torch")
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 6]):
        result = profile._wound_target_with_tracking(
            target,
            attacker.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )

    assert int(result.get("roll", 0) or 0) == 6
    assert "Searing Conflagration" in str(called.get("reason", "") or "")
