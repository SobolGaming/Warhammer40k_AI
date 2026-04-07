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
HUNTING_HOUNDS_DESCRIPTIONS = (
    'While this unit is within 6" of one or more friendly Space Wolves Character models '
    '(excluding Wulfen models), if this unit is not Battle-shocked, HUNTING WOLVES models in it '
    "have an Objective Control characteristic of 1.",
    'While this unit is within 6" of one or more friendly Space Wolves Character models '
    '(excluding Wulfen models), if this unit is not Battle-shocked, Hunting Wolves models in this '
    "unit have an Objective Control characteristic of 1.",
    'While this unit is within 6" of one or more friendly Space Wolves Character models '
    '(excluding Wulfen models), if this unit is not Battle-shocked, models in it have an Objective '
    'Control characteristic of 1.',
)

_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str = "SM", quantity: int | None = None) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id), quantity=quantity)


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
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


def _unit_model_ocs(unit: Unit, *, game_map) -> list[int]:
    return [
        int(unit.get_effective_model_characteristic(model, "objective_control", game_map=game_map) or 0)
        for model in unit.models
    ]


def _effective_oc_for_model_name_fragment(unit: Unit, name_fragment: str, *, game_map) -> int:
    target = name_fragment.lower()
    for model in unit.models:
        if target in str(getattr(model, "name", "") or "").lower():
            return int(unit.get_effective_model_characteristic(model, "objective_control", game_map=game_map) or 0)
    raise AssertionError(f"No model found containing name fragment {name_fragment!r}")


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


def test_fenrisian_wolves_hunting_hounds_sets_all_models_oc_to_one_near_space_wolves_character() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    wolves = _actual_unit("Fenrisian Wolves")
    ragnar = _actual_unit("Ragnar Blackmane")

    sm_army.add_unit(wolves)
    sm_army.add_unit(ragnar)
    _deploy(wolves, 0.0, 0.0)
    _deploy(ragnar, 20.0, 0.0, spacing=0.0)
    game.map.units = [wolves, ragnar]
    game.rebuild_entity_registry()

    assert _unit_model_ocs(wolves, game_map=game.map) == [0] * len(wolves.models)

    _deploy(ragnar, 4.0, 0.0, spacing=0.0)

    assert _unit_model_ocs(wolves, game_map=game.map) == [1] * len(wolves.models)


def test_wolf_guard_headtakers_hunting_hounds_only_sets_hunting_wolves_oc_to_one() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    headtakers = _actual_unit("Wolf Guard Headtakers", quantity=12)
    ragnar = _actual_unit("Ragnar Blackmane")

    sm_army.add_unit(headtakers)
    sm_army.add_unit(ragnar)
    _deploy(headtakers, 0.0, 0.0)
    _deploy(ragnar, 40.0, 0.0, spacing=0.0)
    game.map.units = [headtakers, ragnar]
    game.rebuild_entity_registry()

    assert _effective_oc_for_model_name_fragment(headtakers, "Headtaker", game_map=game.map) == 1
    assert _effective_oc_for_model_name_fragment(headtakers, "Hunting Wolve", game_map=game.map) == 0

    _deploy(ragnar, 4.0, 0.0, spacing=0.0)

    assert _effective_oc_for_model_name_fragment(headtakers, "Headtaker", game_map=game.map) == 1
    assert _effective_oc_for_model_name_fragment(headtakers, "Hunting Wolve", game_map=game.map) == 1


def test_wolf_scouts_hunting_hounds_only_sets_hunting_wolves_oc_to_one() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    scouts = _actual_unit("Wolf Scouts", quantity=12)
    ragnar = _actual_unit("Ragnar Blackmane")

    sm_army.add_unit(scouts)
    sm_army.add_unit(ragnar)
    _deploy(scouts, 0.0, 0.0)
    _deploy(ragnar, 40.0, 0.0, spacing=0.0)
    game.map.units = [scouts, ragnar]
    game.rebuild_entity_registry()

    assert _effective_oc_for_model_name_fragment(scouts, "Wolf Scout", game_map=game.map) == 1
    assert _effective_oc_for_model_name_fragment(scouts, "Hunting Wolve", game_map=game.map) == 0

    _deploy(ragnar, 4.0, 0.0, spacing=0.0)

    assert _effective_oc_for_model_name_fragment(scouts, "Wolf Scout", game_map=game.map) == 1
    assert _effective_oc_for_model_name_fragment(scouts, "Hunting Wolve", game_map=game.map) == 1


def test_hunting_hounds_excludes_wulfen_character_sources() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    wolves = _actual_unit("Fenrisian Wolves")
    murderfang = _actual_unit("Murderfang")

    sm_army.add_unit(wolves)
    sm_army.add_unit(murderfang)
    _deploy(wolves, 0.0, 0.0)
    _deploy(murderfang, 20.0, 0.0, spacing=0.0)
    game.map.units = [wolves, murderfang]
    game.rebuild_entity_registry()

    _deploy(murderfang, 4.0, 0.0, spacing=0.0)

    assert _unit_model_ocs(wolves, game_map=game.map) == [0] * len(wolves.models)


def test_hunting_hounds_does_not_apply_while_battle_shocked() -> None:
    game, _sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    wolves = _actual_unit("Fenrisian Wolves")
    ragnar = _actual_unit("Ragnar Blackmane")

    sm_army.add_unit(wolves)
    sm_army.add_unit(ragnar)
    _deploy(wolves, 0.0, 0.0)
    _deploy(ragnar, 4.0, 0.0, spacing=0.0)
    game.map.units = [wolves, ragnar]
    game.rebuild_entity_registry()

    wolves.apply_status_effect(BattleShockEffect(current_turn=1))

    assert _unit_model_ocs(wolves, game_map=game.map) == [0] * len(wolves.models)


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


def test_support_matrix_classifies_hunting_hounds_variants_as_supported() -> None:
    gsm = _seed_support_maps()

    for description in HUNTING_HOUNDS_DESCRIPTIONS:
        status, notes = gsm._classify_ability("Hunting Hounds", description, faction_id="SM")

        assert status == "Supported"
        lowered = str(notes or "").lower()
        assert "space wolves character" in lowered
        assert "wulfen" in lowered
        assert "objective control 1" in lowered or "objective control" in lowered
