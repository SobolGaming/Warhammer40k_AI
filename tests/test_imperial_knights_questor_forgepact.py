from __future__ import annotations

import pytest

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army, ArmyValidationError
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str,
        keywords=None,
        faction_keywords=None,
        cost: int = 100,
        wounds: int = 12,
    ):
        self.id = name.lower().replace(" ", "-")
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": int(cost)}]
        self.datasheets_models = [
            {
                "M": "10",
                "T": "10",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "6",
                "OC": "8",
                "base_size": "100mm",
                "inv_sv": "5",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str,
    keywords=None,
    faction_keywords=None,
    cost: int = 100,
    wounds: int = 12,
) -> Unit:
    unit = Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            cost=cost,
            wounds=wounds,
        )
    )
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game(*, points_limit: int = 2000):
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ik_army = Army("Imperial Knights", detachment_type="Questor Forgepact")
    ik_army.faction_id = "QI"
    ik_army.points_limit = int(points_limit)
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "SM"
    ik_player = Player("IK", PlayerControl.REMOTE, army=ik_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ik_player)
    game.add_player(enemy_player)
    return game, ik_army, enemy_army, ik_player, enemy_player


def _make_ranged_profile(*, strength: str = "4") -> WargearProfile:
    parent = type(
        "_ParentWargear",
        (),
        {
            "name": "Test Carbine",
            "is_melee": staticmethod(lambda: False),
            "is_ranged": staticmethod(lambda: True),
        },
    )()
    data = {
        "range": "24",
        "A": "1",
        "BS_WS": "3+",
        "S": str(strength),
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Test Carbine", wargear_data=data, parent_wargear=parent)


def test_questor_forgepact_sacristan_pledge_heals_one_lost_wound():
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Paladin",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    ik_army.add_unit(knight)
    game.map.units = [knight]
    knight.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    knight.models[0].wounds = 9

    mgr = ik_army.imperial_knights_detachments
    mgr.on_command_phase_start(game=game, player=ik_player)

    assert int(knight.models[0].wounds or 0) == 10


def test_questor_forgepact_sacristan_pledge_uses_d3_with_tech_priest_support(monkeypatch):
    game, ik_army, _enemy_army, ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Errant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    dominus = _make_unit(
        "Tech-priest Dominus",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "TECH-PRIEST", "CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=5,
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(dominus)
    game.map.units = [knight, dominus]
    knight.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    dominus.models[0].set_location(2.0, 0.0, 0.0, 0.0)
    knight.models[0].wounds = 7

    monkeypatch.setattr(
        "warhammer40k_ai.rules.imperial_knights_detachments.get_roll",
        lambda _expr: 3,
    )
    mgr = ik_army.imperial_knights_detachments
    mgr.on_command_phase_start(game=game, player=ik_player)

    assert int(knight.models[0].wounds or 0) == 10


def test_questor_forgepact_divine_inspiration_rerolls_hit_and_wound_ones_within_6_of_knight():
    game, ik_army, enemy_army, _ik_player, _enemy_player = _build_game()
    skitarii = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        wounds=10,
    )
    knight = _make_unit(
        "Knight Warden",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        wounds=12,
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Space Marines",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=10,
    )
    ik_army.add_unit(skitarii)
    ik_army.add_unit(knight)
    enemy_army.add_unit(enemy)
    game.map.units = [skitarii, knight, enemy]
    skitarii.models[0].set_location(0.0, 0.0, 0.0, 0.0)
    knight.models[0].set_location(5.0, 0.0, 0.0, 0.0)
    enemy.models[0].set_location(10.0, 0.0, 0.0, 0.0)

    profile = _make_ranged_profile(strength="5")
    hit_result = profile._hit_target_with_tracking(
        enemy,
        skitarii.models[0],
        {"distance_to_target": 10.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )
    wound_result = profile._wound_target_with_tracking(
        enemy,
        skitarii.models[0],
        {"distance_to_target": 10.0},
        roll_value=1,
        allow_rerolls=True,
        log_roll=False,
    )

    assert 1 in list(hit_result.get("reroll_values", []) or [])
    assert any("Divine Inspiration" in str(reason) for reason in list(hit_result.get("reroll_value_reasons", []) or []))
    assert 1 in list(wound_result.get("reroll_values", []) or [])
    assert any("Divine Inspiration" in str(reason) for reason in list(wound_result.get("reroll_value_reasons", []) or []))


def test_questor_forgepact_validate_detachment_rules_rejects_non_allowed_admech_unit():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Gallant",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    illegal_admech = _make_unit(
        "Kataphron Breachers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(illegal_admech)

    with pytest.raises(ArmyValidationError):
        ik_army.validate_detachment_rules()


def test_questor_forgepact_validate_detachment_rules_rejects_admech_warlord():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game()
    knight = _make_unit(
        "Knight Castellan",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
    )
    admech = _make_unit(
        "Skitarii Marshal",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "CHARACTER", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(admech)
    admech.is_warlord = True
    ik_army.warlord = admech

    with pytest.raises(ArmyValidationError):
        ik_army.validate_detachment_rules()


def test_questor_forgepact_validate_detachment_rules_rejects_allied_points_cap():
    _game, ik_army, _enemy_army, _ik_player, _enemy_player = _build_game(points_limit=1000)
    knight = _make_unit(
        "Knight Crusader",
        faction_name="Imperial Knights",
        keywords=["IMPERIAL KNIGHTS", "VEHICLE"],
        faction_keywords=["IMPERIAL KNIGHTS"],
        cost=400,
    )
    admech_a = _make_unit(
        "Skitarii Rangers",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        cost=150,
    )
    admech_b = _make_unit(
        "Skitarii Vanguard",
        faction_name="Adeptus Mechanicus",
        keywords=["ADEPTUS MECHANICUS", "INFANTRY"],
        faction_keywords=["ADEPTUS MECHANICUS"],
        cost=150,
    )
    ik_army.add_unit(knight)
    ik_army.add_unit(admech_a)
    ik_army.add_unit(admech_b)

    with pytest.raises(ArmyValidationError):
        ik_army.validate_detachment_rules()
