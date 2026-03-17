from __future__ import annotations

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 1
    game.phase = BattleRoundPhases.FIGHT_PHASE
    return game, sm_army, sm_player


def _deploy(unit: Unit, x: float, y: float) -> None:
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        alive_attr = getattr(model, "is_alive", False)
        alive = bool(alive_attr() if callable(alive_attr) else alive_attr)
        if not alive:
            continue
        model.set_location(float(x) + float(idx) * 0.1, float(y), 0.0, 0.0)


def test_ravenwing_black_knights_gain_anti_keywords_when_selected_to_fight_after_charge() -> None:
    game, sm_army, sm_player = _build_game()
    black_knights = _actual_unit("Ravenwing Black Knights", datasheet_id="000000241")
    sm_army.add_unit(black_knights)
    _deploy(black_knights, 0.0, 0.0)
    game.map.units = [black_knights]
    game.rebuild_entity_registry()

    black_knights.round_state.charged_this_round = True
    game._on_fight_unit_selected_charged_melee_weapon_keywords(unit=black_knights, selecting_player=sm_player)

    model = black_knights.models[0]
    melee_weapons = [
        str(getattr(wargear, "name", "") or "").strip()
        for wargear in list(getattr(model, "wargear", []) or [])
        if wargear is not None and hasattr(wargear, "is_melee") and wargear.is_melee()
    ]
    assert melee_weapons

    keyword_rules = model.get_temporary_weapon_keyword_bonuses(melee_weapons[0])
    keywords = {str(rule.get("keyword", "") or "").upper() for rule in list(keyword_rules or [])}
    assert "ANTI MONSTER 4" in keywords
    assert "ANTI VEHICLE 4" in keywords
    assert any("knights of caliban" in str(rule.get("source", "") or "").lower() for rule in list(keyword_rules or []))


def test_ravenwing_black_knights_do_not_gain_keywords_without_charge() -> None:
    game, sm_army, sm_player = _build_game()
    black_knights = _actual_unit("Ravenwing Black Knights", datasheet_id="000000241")
    sm_army.add_unit(black_knights)
    _deploy(black_knights, 0.0, 0.0)
    game.map.units = [black_knights]
    game.rebuild_entity_registry()

    black_knights.round_state.charged_this_round = False
    game._on_fight_unit_selected_charged_melee_weapon_keywords(unit=black_knights, selecting_player=sm_player)

    model = black_knights.models[0]
    melee_weapons = [
        str(getattr(wargear, "name", "") or "").strip()
        for wargear in list(getattr(model, "wargear", []) or [])
        if wargear is not None and hasattr(wargear, "is_melee") and wargear.is_melee()
    ]
    assert melee_weapons
    assert model.get_temporary_weapon_keyword_bonuses(melee_weapons[0]) == []
