from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


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
    necron_army = Army("Necrons", "Cryptek Conclave")
    necron_army.faction_id = "NEC"
    enemy_army = Army("Enemy", "Other")
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
    return game, necron_player, enemy_player


def test_technosorcerous_augmentations_grants_assault_to_cryptek_model_weapons():
    cryptek = _create_unit(
        "Technomancer",
        keywords=["CRYPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    warriors = _create_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    _game, _p1, _p2 = _build_game(necron_units=[cryptek, warriors], enemy_units=[enemy])

    cryptek_weapon = SimpleNamespace(name="Eldritch Lance", is_ranged=lambda: True, is_melee=lambda: False)
    warrior_weapon = SimpleNamespace(name="Gauss Flayer", is_ranged=lambda: True, is_melee=lambda: False)
    cryptek.models[0].wargear = [cryptek_weapon]
    warriors.models[0].wargear = [warrior_weapon]

    cryptek_profile = _make_ranged_profile(cryptek_weapon)
    warrior_profile = _make_ranged_profile(warrior_weapon)

    assert bool(cryptek.can_shoot_after_advance(cryptek_profile))
    assert not bool(warriors.can_shoot_after_advance(warrior_profile))


def test_technosorcerous_augmentations_choice_applies_selected_keyword():
    cryptek = _create_unit(
        "Technomancer",
        keywords=["CRYPTEK", "INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, necron_player, _enemy_player = _build_game(necron_units=[cryptek], enemy_units=[enemy])

    cryptek_weapon = SimpleNamespace(name="Eldritch Lance", is_ranged=lambda: True, is_melee=lambda: False)
    cryptek.models[0].wargear = [cryptek_weapon]

    game._on_shooting_targets_selected_technosorcerous_augmentations(attacking_unit=cryptek, target_units=[enemy])
    pending = list(game.decision_queue.list() or [])
    assert pending
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_TECHNOSORCEROUS_AUGMENTATION

    choices = [str((opt.payload or {}).get("choice", "") or "") for opt in list(request.options or [])]
    assert choices == ["ANTI_INFANTRY_3", "ANTI_MOUNTED_4", "ASSAULT", "HEAVY", "IGNORES_COVER"]

    anti_infantry_option_id = next(
        opt.option_id
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("choice", "") or "") == "ANTI_INFANTRY_3"
    )
    resolve_decision_command(game, request, anti_infantry_option_id, player_id=necron_player.id)

    bonuses = cryptek.get_model_weapon_keyword_bonuses(
        model=cryptek.models[0],
        weapon_name="Eldritch Lance",
        attack_type="ranged",
    )
    assert ("INFANTRY", 3) in list(bonuses.get("anti_specs", []) or [])


def test_technosorcerous_augmentations_only_triggers_for_cryptek_units():
    warriors = _create_unit(
        "Necron Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["NECRONS"],
    )
    enemy = _create_unit("Enemy Unit", keywords=["INFANTRY"])
    game, _p1, _p2 = _build_game(necron_units=[warriors], enemy_units=[enemy])

    game._on_shooting_targets_selected_technosorcerous_augmentations(attacking_unit=warriors, target_units=[enemy])
    assert list(game.decision_queue.list() or []) == []
