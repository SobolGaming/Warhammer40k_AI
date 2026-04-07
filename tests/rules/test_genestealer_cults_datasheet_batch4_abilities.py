from types import SimpleNamespace

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"
    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"

    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    game.add_player(enemy_player)
    game.add_player(gsc_player)
    return game, enemy_player, gsc_player, enemy_army, gsc_army


def test_lictor_pheromone_trail_allows_rapid_ingress_zero_cp_once_per_battle_round() -> None:
    game, _enemy_player, gsc_player, _enemy_army, gsc_army = _build_game()

    lictor = _actual_unit("Lictor", faction_id="GC")
    gsc_army.add_unit(lictor)
    lictor.deployed = False
    lictor.reserve_status = "reserves"

    stratagem = SimpleNamespace(name="Rapid Ingress", cp_cost=1)

    preview = gsc_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=lictor,
        assume_optional_discounts=True,
    )
    assert int(preview.get("cost", -1)) == 0

    gsc_player.set_next_optional_decision("PHEROMONE_TRAIL_RAPID_INGRESS", True)
    first = gsc_player.apply_stratagem_cp_cost(stratagem, target_unit=lictor)
    assert int(first.get("cost", -1)) == 0
    assert bool(first.get("pheromone_trail_rapid_ingress_use", False)) is True
    assert bool(lictor.pheromone_trail_used_this_battle_round(game)) is True

    gsc_player.set_next_optional_decision("PHEROMONE_TRAIL_RAPID_INGRESS", True)
    second = gsc_player.apply_stratagem_cp_cost(stratagem, target_unit=lictor)
    assert int(second.get("cost", -1)) == 1
    assert bool(second.get("pheromone_trail_rapid_ingress_use", False)) is False

    game.turn = 2
    preview_next_round = gsc_player.preview_stratagem_cp_cost(
        stratagem,
        target_unit=lictor,
        assume_optional_discounts=True,
    )
    assert int(preview_next_round.get("cost", -1)) == 0
