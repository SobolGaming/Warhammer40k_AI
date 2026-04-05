from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    gsc_army = Army("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[gsc_player, enemy_player])
    game.turn = 2
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _find_loping_speed_request(game: Game):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CONFIRM_YES_NO
            and str((getattr(req, "context", {}) or {}).get("reactive_move_kind", "") or "") == "loping_speed"
        ),
        None,
    )


def _equip_cult_sniper_rifle(sanctus: Unit) -> None:
    sanctus.models[0].wargear = [
        Wargear(
            {
                "name": "Cult sniper rifle",
                "type": "Ranged",
                "range": "36",
                "A": "1",
                "BS_WS": "3+",
                "S": "7",
                "AP": "-2",
                "D": "3",
                "description": "anti-psyker 2+, heavy, precision",
            }
        ),
        Wargear(
            {
                "name": "Close combat weapon",
                "type": "Melee",
                "range": "Melee",
                "A": "2",
                "BS_WS": "3+",
                "S": "3",
                "AP": "0",
                "D": "1",
                "description": "",
            }
        ),
    ]
    sanctus._ability_cache = {}


def test_sanctus_default_loadout_enables_cloaked_assassin_but_not_creeping_shadow() -> None:
    sanctus = _actual_unit("Sanctus", faction_id="GC")

    assert sanctus.get_loping_speed_rule() is None
    rule = sanctus.get_datasheet_no_fire_overwatch_rule()
    assert rule is not None
    assert str(rule.get("source", "") or "") == "Cloaked Assassin"


def test_sanctus_cult_sniper_rifle_loadout_enables_creeping_shadow_and_disables_cloaked_assassin() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    sanctus = _actual_unit("Sanctus", faction_id="GC")
    _equip_cult_sniper_rifle(sanctus)
    enemy = _actual_unit("Warboss", faction_id="ORK")

    gsc_army.add_unit(sanctus)
    enemy_army.add_unit(enemy)
    _deploy(sanctus, 0.0, 0.0, spacing=0.0)
    _deploy(enemy, 8.0, 0.0, spacing=0.0)
    game.map.units = [sanctus, enemy]
    game.rebuild_entity_registry()

    rule = sanctus.get_loping_speed_rule()
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Creeping Shadow"
    assert int(rule.get("range", 0) or 0) == 9
    assert int(rule.get("max_distance", 0) or 0) == 6
    assert sanctus.get_datasheet_no_fire_overwatch_rule() is None

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    request = _find_loping_speed_request(game)
    assert request is not None
    assert str(getattr(request, "player_id", "") or "") == str(gsc_player.id)
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("reactive_move_kind", "") or "") == "loping_speed"
    assert str(ctx.get("reactive_move_unit_id", "") or "") == str(get_entity_id(sanctus) or "")
    assert str(ctx.get("reactive_move_moving_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    assert "Creeping Shadow" in str(ctx.get("message", "") or "")
