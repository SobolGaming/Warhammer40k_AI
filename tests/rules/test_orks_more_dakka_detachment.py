from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        slug = str(name or "unit").lower().replace(" ", "-")
        self.id = f"mock-{slug}"
        self.name = name
        self.faction_data = {"name": "Test"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _create_unit(name: str, *, keywords=None, faction_keywords=None) -> Unit:
    unit = Unit(_MockDatasheet(name, keywords=keywords, faction_keywords=faction_keywords))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _make_ranged_profile() -> WargearProfile:
    parent = SimpleNamespace(
        name="Shoota",
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    data = {
        "range": "24",
        "A": "2",
        "BS_WS": "5+",
        "S": "5",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    return WargearProfile("Profile", wargear_data=data, parent_wargear=parent)


def _build_game(*, ork_unit: Unit, enemy_unit: Unit):
    ork_army = Army.with_detachment("Orks", "More Dakka!")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"
    ork_army.add_unit(ork_unit)
    enemy_army.add_unit(enemy_unit)

    ork_player = Player("Ork Player", control=PlayerControl.LOCAL, army=ork_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
    return game, ork_army, ork_player


def test_more_dakka_grants_shoot_after_advance_for_orks_infantry():
    unit = _create_unit("Boyz", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    _game, _army, _player = _build_game(ork_unit=unit, enemy_unit=enemy)
    profile = _make_ranged_profile()

    assert unit.can_shoot_after_advance(profile) is True


def test_more_dakka_grants_shoot_after_fall_back_for_orks_infantry():
    unit = _create_unit("Boyz", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    _game, _army, _player = _build_game(ork_unit=unit, enemy_unit=enemy)
    profile = _make_ranged_profile()

    assert unit.can_shoot_after_fall_back(profile) is True


def test_more_dakka_shoot_after_advance_does_not_apply_to_non_infantry_non_walker():
    unit = _create_unit("Warbikers", keywords=["ORKS", "MOUNTED"], faction_keywords=["ORKS"])
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    _game, _army, _player = _build_game(ork_unit=unit, enemy_unit=enemy)
    profile = _make_ranged_profile()

    assert unit.can_shoot_after_advance(profile) is False
    assert unit.can_shoot_after_fall_back(profile) is False


def test_more_dakka_grants_sustained_hits_while_waaagh_active_in_shooting_phase():
    attacker_unit = _create_unit("Boyz", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"])
    target_unit = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    game, ork_army, _ork_player = _build_game(ork_unit=attacker_unit, enemy_unit=target_unit)
    game.phase = SimpleNamespace(name="SHOOTING_PHASE")
    ork_army.waaagh.active = True
    ork_army.waaagh.active_scope = "all"

    profile = _make_ranged_profile()
    attack_instance = {}
    hit_result = profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert bool(hit_result.get("hit"))
    assert int(attack_instance.get("sustained_hit", 0) or 0) == 1
    assert any("Dakka! Dakka! Dakka!" in str(entry) for entry in hit_result.get("special_effects", []))


def test_more_dakka_sustained_hits_do_not_apply_outside_shooting_phase():
    attacker_unit = _create_unit("Boyz", keywords=["ORKS", "INFANTRY", "BOYZ"], faction_keywords=["ORKS"])
    target_unit = _create_unit("Enemy Unit", keywords=["INFANTRY"], faction_keywords=["ADEPTUS ASTARTES"])
    game, ork_army, _ork_player = _build_game(ork_unit=attacker_unit, enemy_unit=target_unit)
    game.phase = SimpleNamespace(name="FIGHT_PHASE")
    ork_army.waaagh.active = True
    ork_army.waaagh.active_scope = "all"

    profile = _make_ranged_profile()
    attack_instance = {}
    profile._hit_target_with_tracking(
        target_unit,
        attacker_unit.models[0],
        attack_instance,
        roll_value=6,
        allow_rerolls=False,
        log_roll=False,
    )

    assert int(attack_instance.get("sustained_hit", 0) or 0) == 0
