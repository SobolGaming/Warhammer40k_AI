from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(self, name: str, *, keywords=None, faction_keywords=None):
        self.id = f"mock-{name.lower().replace(' ', '-')}"
        self.name = name
        self.faction_data = {"name": "Necrons"}
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


def _make_ranged_profile(weapon) -> WargearProfile:
    return WargearProfile(
        "Profile",
        wargear_data={
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=weapon,
    )


def _build_game(*, necron_units: list[Unit], enemy_units: list[Unit]):
    necron_army = Army.with_detachment("Necrons", "Cursed Legion")
    necron_army.faction_id = "NEC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ENEMY"

    for unit in list(necron_units or []):
        necron_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"
    for unit in list(enemy_units or []):
        enemy_army.add_unit(unit)
        unit.deployed = True
        unit.reserve_status = "deployed"

    necron_player = Player("Necron Player", control=PlayerControl.LOCAL, army=necron_army)
    enemy_player = Player("Enemy Player", control=PlayerControl.REMOTE, army=enemy_army)

    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.add_player(necron_player)
    game.add_player(enemy_player)
    game.current_player_idx = 0
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game.map.units = list(necron_units or []) + list(enemy_units or [])
    game.rebuild_entity_registry()
    return game


def _set_mock_below_half(unit, value: bool) -> None:
    unit._test_below_half = bool(value)
    unit.is_below_half_strength = lambda: bool(getattr(unit, "_test_below_half", False))


def test_cold_fervour_applies_destroyer_cult_strength_bonus_in_attack_resolution():
    destroyers = _create_unit(
        "Skorpekh Destroyers",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game = _build_game(necron_units=[destroyers], enemy_units=[enemy])

    weapon = SimpleNamespace(name="Gauss Blaster", is_ranged=lambda: True, is_melee=lambda: False)
    destroyers.models[0].wargear = [weapon]
    profile = _make_ranged_profile(weapon)

    result = profile._wound_target_with_tracking(
        enemy,
        destroyers.models[0],
        {},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    modifiers = " ".join(str(item) for item in list(result.get("modifiers", []) or []))
    assert "Cold Fervour" in modifiers


def test_cold_fervour_secondary_bonus_activates_when_destroyer_causes_below_half():
    destroyers = _create_unit(
        "Lokhust Destroyers",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    warriors = _create_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    tomb_stalker = _create_unit(
        "Tomb Sentinel",
        keywords=["MONSTER"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_mock_below_half(enemy, False)
    game = _build_game(necron_units=[destroyers, warriors, tomb_stalker], enemy_units=[enemy])

    game._on_shooting_targets_selected_cold_fervour(attacking_unit=destroyers, target_units=[enemy])
    _set_mock_below_half(enemy, True)
    game._on_unit_shooting_resolved_cold_fervour(attacker_unit=destroyers, hits_by_target={enemy: 1})

    mgr = getattr(destroyers.get_parent_army(), "necrons_detachments", None)
    warrior_weapon = SimpleNamespace(name="Gauss Flayer", is_ranged=lambda: True, is_melee=lambda: False)
    warriors.models[0].wargear = [warrior_weapon]
    warrior_profile = _make_ranged_profile(warrior_weapon)
    warrior_bonus, _source = mgr.cold_fervour_strength_bonus(warriors.models[0], warrior_profile, game=game)
    assert int(warrior_bonus) == 2

    monster_weapon = SimpleNamespace(name="Particle Emitter", is_ranged=lambda: True, is_melee=lambda: False)
    tomb_stalker.models[0].wargear = [monster_weapon]
    monster_profile = _make_ranged_profile(monster_weapon)
    monster_bonus, _source = mgr.cold_fervour_strength_bonus(tomb_stalker.models[0], monster_profile, game=game)
    assert int(monster_bonus) == 0


def test_cold_fervour_does_not_trigger_when_target_was_already_below_half():
    destroyers = _create_unit(
        "Lokhust Destroyers",
        keywords=["DESTROYER CULT", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    warriors = _create_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _set_mock_below_half(enemy, True)
    game = _build_game(necron_units=[destroyers, warriors], enemy_units=[enemy])

    game._on_shooting_targets_selected_cold_fervour(attacking_unit=destroyers, target_units=[enemy])
    game._on_unit_shooting_resolved_cold_fervour(attacker_unit=destroyers, hits_by_target={enemy: 1})

    mgr = getattr(destroyers.get_parent_army(), "necrons_detachments", None)
    warrior_weapon = SimpleNamespace(name="Gauss Flayer", is_ranged=lambda: True, is_melee=lambda: False)
    warriors.models[0].wargear = [warrior_weapon]
    warrior_profile = _make_ranged_profile(warrior_weapon)
    warrior_bonus, _source = mgr.cold_fervour_strength_bonus(warriors.models[0], warrior_profile, game=game)
    assert int(warrior_bonus) == 0

