from __future__ import annotations

import os

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.status_effects import BattleShockEffect
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


CURSE_OF_THE_WULFEN_DESCRIPTION = (
    'While this unit is within 6" of one or more friendly Space Wolves Character models '
    '(excluding Wulfen models) or within 12" of one or more friendly Wolf Priest models, if it is '
    "not Battle-shocked, add 1 to the Objective Control characteristic of Infantry models in it and "
    "add 3 to the Objective Control characteristic of Vehicle models in it."
)

_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str = "SM") -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[sm_player, enemy_player])
    game.current_player_index = 0
    game.turn = 1
    return game, sm_player, enemy_player, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for index, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(index) * float(spacing)), float(y), 0.0, 0.0)


def _effective_oc(unit: Unit, *, game_map) -> int:
    return int(unit.get_effective_model_characteristic(unit.models[0], "objective_control", game_map=game_map) or 0)


def _seed_support_maps():
    import scripts.generate_ability_support_matrix as gsm

    abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Abilities.json"))
    detachment_abilities = gsm._read_json(os.path.join(gsm.WAHA_DIR, "Detachment_abilities.json"))
    gsm.DETACHMENT_ABILITY_IDS = {
        str(row.get("id", "") or "").strip()
        for row in detachment_abilities
        if str(row.get("id", "") or "").strip()
    }
    gsm._seed_ability_support_maps(abilities, detachment_abilities)
    return gsm


def test_wulfen_infantry_gets_plus_one_oc_near_space_wolves_character() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    wulfen = _actual_unit("Wulfen")
    ragnar = _actual_unit("Ragnar Blackmane")

    sm_army.add_unit(wulfen)
    sm_army.add_unit(ragnar)
    _deploy(wulfen, 0.0, 0.0)
    _deploy(ragnar, 20.0, 0.0, spacing=0.0)
    game.map.units = [wulfen, ragnar]
    game.rebuild_entity_registry()

    base_oc = _effective_oc(wulfen, game_map=game.map)

    _deploy(ragnar, 4.0, 0.0, spacing=0.0)
    buffed_oc = _effective_oc(wulfen, game_map=game.map)

    assert buffed_oc == base_oc + 1


def test_wulfen_dreadnought_gets_plus_three_oc_near_wolf_priest_outside_character_range() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    dreadnought = _actual_unit("Wulfen Dreadnought")
    wolf_priest = _actual_unit("Wolf Priest")

    sm_army.add_unit(dreadnought)
    sm_army.add_unit(wolf_priest)
    _deploy(dreadnought, 0.0, 0.0, spacing=0.0)
    _deploy(wolf_priest, 20.0, 0.0, spacing=0.0)
    game.map.units = [dreadnought, wolf_priest]
    game.rebuild_entity_registry()

    base_oc = _effective_oc(dreadnought, game_map=game.map)

    _deploy(wolf_priest, 10.0, 0.0, spacing=0.0)
    buffed_oc = _effective_oc(dreadnought, game_map=game.map)

    assert buffed_oc == base_oc + 3


def test_curse_of_the_wulfen_excludes_wulfen_character_sources() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    wulfen = _actual_unit("Wulfen")
    murderfang = _actual_unit("Murderfang")

    sm_army.add_unit(wulfen)
    sm_army.add_unit(murderfang)
    _deploy(wulfen, 0.0, 0.0)
    _deploy(murderfang, 20.0, 0.0, spacing=0.0)
    game.map.units = [wulfen, murderfang]
    game.rebuild_entity_registry()

    base_oc = _effective_oc(wulfen, game_map=game.map)

    _deploy(murderfang, 4.0, 0.0, spacing=0.0)
    buffed_oc = _effective_oc(wulfen, game_map=game.map)

    assert buffed_oc == base_oc


def test_curse_of_the_wulfen_does_not_apply_while_battle_shocked() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    dreadnought = _actual_unit("Wulfen Dreadnought")
    wolf_priest = _actual_unit("Wolf Priest")

    sm_army.add_unit(dreadnought)
    sm_army.add_unit(wolf_priest)
    _deploy(dreadnought, 0.0, 0.0, spacing=0.0)
    _deploy(wolf_priest, 10.0, 0.0, spacing=0.0)
    game.map.units = [dreadnought, wolf_priest]
    game.rebuild_entity_registry()

    dreadnought.apply_status_effect(BattleShockEffect(current_turn=1))

    assert _effective_oc(dreadnought, game_map=game.map) == 0


def test_support_matrix_classifies_curse_of_the_wulfen_as_supported() -> None:
    gsm = _seed_support_maps()
    status, notes = gsm._classify_ability(
        "Curse of the Wulfen",
        CURSE_OF_THE_WULFEN_DESCRIPTION,
        faction_id="SM",
    )

    assert status == "Supported"
    lowered = str(notes or "").lower()
    assert "space wolves character" in lowered
    assert "+1 objective control" in lowered or "+1 oc" in lowered
    assert "+3" in lowered
