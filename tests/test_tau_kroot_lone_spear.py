from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        ds_id: str = "",
        abilities=None,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
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
        self.attached_to = []


def _make_unit(name: str, *, abilities=None, keywords=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities, keywords=keywords)
    return Unit(datasheet)


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


def _make_profile():
    from warhammer40k_ai.units.wargear import WargearProfile

    parent = SimpleNamespace(name="Test Rifle", is_melee=lambda: False, is_ranged=lambda: True)
    return WargearProfile(
        profile_name="Ranged",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=parent,
    )


def test_tau_advanced_scouting_marks_and_grants_other_kroot_hit_rerolls():
    from warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin import GameShootingFightHandlersMixin

    advanced_scouting = {
        "name": "Advanced Scouting",
        "description": (
            "Each time this model makes a ranged attack that hits an enemy unit, until the end of the turn, "
            "each time another Kroot model from your army makes an attack that targets that enemy unit, "
            "you can re-roll the Hit roll."
        ),
        "type": "Datasheet",
        "parameter": "",
    }

    lone_spear = _make_unit("Kroot Lone-Spear", abilities=[advanced_scouting], keywords=["KROOT"])
    friendly_kroot = _make_unit("Kroot Carnivores", keywords=["KROOT"])
    friendly_non_kroot = _make_unit("Strike Team", keywords=["INFANTRY"])
    enemy = _make_unit("Enemy Unit", keywords=["INFANTRY"])

    attacker_player = SimpleNamespace(id="P1")
    defender_player = SimpleNamespace(id="P2")
    game_stub = SimpleNamespace(
        turn=1,
        phase=SimpleNamespace(name="SHOOTING_PHASE"),
        is_shooting_phase=lambda: True,
        get_current_player=lambda: attacker_player,
    )
    attacker_player.game = game_stub
    defender_player.game = game_stub

    attacker_army = SimpleNamespace(player=attacker_player)
    defender_army = SimpleNamespace(player=defender_player)
    lone_spear.set_parent_army(attacker_army)
    friendly_kroot.set_parent_army(attacker_army)
    friendly_non_kroot.set_parent_army(attacker_army)
    enemy.set_parent_army(defender_army)

    GameShootingFightHandlersMixin._on_unit_shooting_resolved_tau_advanced_scouting(
        game_stub,
        attacker_unit=lone_spear,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {lone_spear.models[0]}},
    )

    marks = list(enemy.special_rules.get("tau_advanced_scouting_marks", []) or [])
    assert len(marks) == 1
    assert str(marks[0].get("keyword_phrase", "")).lower() == "kroot"

    profile = _make_profile()

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2, 4]):
        kroot_result = profile._hit_target_with_tracking(enemy, friendly_kroot.models[0], {"_aura_attack_mods": _aura_stub()})
    assert int(kroot_result["roll"]) == 4
    assert bool(kroot_result["hit"])
    assert any("Advanced Scouting" in effect for effect in list(kroot_result.get("special_effects", []) or []))

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2]):
        source_result = profile._hit_target_with_tracking(enemy, lone_spear.models[0], {"_aura_attack_mods": _aura_stub()})
    assert int(source_result["roll"]) == 2
    assert not bool(source_result["hit"])

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2]):
        non_kroot_result = profile._hit_target_with_tracking(enemy, friendly_non_kroot.models[0], {"_aura_attack_mods": _aura_stub()})
    assert int(non_kroot_result["roll"]) == 2
    assert not bool(non_kroot_result["hit"])

    game_stub.turn = 2
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2]):
        expired_result = profile._hit_target_with_tracking(enemy, friendly_kroot.models[0], {"_aura_attack_mods": _aura_stub()})
    assert int(expired_result["roll"]) == 2
    assert not bool(expired_result["hit"])
    assert not bool(enemy.special_rules.get("tau_advanced_scouting_marks"))
