from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_battleshock_test_reroll_sources
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, datasheet_id: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, datasheet_id=datasheet_id, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army


def _deploy(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(unit.models or [])):
        model.set_location(x + (index * 0.1), y, 0.0, 0.0)


def test_the_sanguinor_aura_of_fervour_grants_battleshock_reroll_aura() -> None:
    game, sm_army, _enemy_army = _build_game()
    sanguinor = _actual_unit("The Sanguinor", datasheet_id="000000156")
    nearby_ally = _actual_unit("Scout Squad", datasheet_id="000001160")
    far_ally = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(sanguinor)
    sm_army.add_unit(nearby_ally)
    sm_army.add_unit(far_ally)
    _deploy(sanguinor, 10.0, 10.0)
    _deploy(nearby_ally, 14.5, 10.0)
    _deploy(far_ally, 18.0, 10.0)
    game.map.units = [sanguinor, nearby_ally, far_ally]
    game.rebuild_entity_registry()

    nearby_sources = get_aura_battleshock_test_reroll_sources(nearby_ally, game_map=game.map)
    far_sources = get_aura_battleshock_test_reroll_sources(far_ally, game_map=game.map)

    assert "Aura of Fervour (Aura)" in nearby_sources
    assert "Aura of Fervour (Aura)" not in far_sources


def test_the_sanguinor_aura_of_fervour_rerolls_leadership_tests() -> None:
    game, sm_army, _enemy_army = _build_game()
    sanguinor = _actual_unit("The Sanguinor", datasheet_id="000000156")
    ally = _actual_unit("Scout Squad", datasheet_id="000001160")
    sm_army.add_unit(sanguinor)
    sm_army.add_unit(ally)
    _deploy(sanguinor, 10.0, 10.0)
    _deploy(ally, 14.5, 10.0)
    game.map.units = [sanguinor, ally]
    game.rebuild_entity_registry()

    with patch("warhammer40k_ai.units.unit_mixins.state_attachment_mixin.get_roll", side_effect=[11, 6]):
        assert ally.pass_leadership_check() is True
