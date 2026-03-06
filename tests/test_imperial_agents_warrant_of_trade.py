from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_WARRANT_OF_TRADE_ABILITY = {
    "name": "Warrant of Trade",
    "description": (
        "If your army includes one or more units with this ability, after both players have deployed their armies, "
        "select upto D3 IMpERIUM BATTlElINE units from your army and redeploy them. When doing so, you can set those "
        "units up in Strategic Reserves, regardless of how many units are already in Strategic Reserves."
    ),
    "type": "Datasheet",
    "parameter": "",
}


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        datasheet_id: str,
        *,
        keywords=None,
        faction_keywords=None,
        abilities=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": "Imperial Agents"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AGENTS OF THE IMPERIUM", "IMPERIUM"])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "3",
                "Sv": "4",
                "W": "3",
                "Ld": "7",
                "OC": "1",
                "base_size": "28mm",
                "inv_sv": "7",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
        )
    )


def _mark_deployed(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army("Imperial Agents", "Imperialis Fleet")
    ia_army.faction_id = "AOI"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("Imperial Agents", control=PlayerControl.REMOTE, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    game.attacker_index = 0
    game.defender_index = 1
    return game, ia_player, enemy_player, ia_army, enemy_army


def _find_warrant_request(game: Game, *, player_id: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "") != "aeldari_guileful_strategist":
            continue
        if str(ctx.get("ability_name", "") or "") != "Warrant of Trade":
            continue
        return req
    return None


def _find_skip_option_id(request) -> str:
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == "skip":
            return str(getattr(option, "option_id", "") or "")
    return ""


def _find_option_id(request, *, target_unit_id: str, action: str) -> str:
    target_id = str(target_unit_id or "")
    action_norm = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("target_unit_id", "") or "") != target_id:
            continue
        if str(payload.get("redeploy_action", "") or "").strip().lower() != action_norm:
            continue
        return str(getattr(option, "option_id", "") or "")
    return ""


def test_warrant_of_trade_parses_redeploy_filter_and_army_once():
    source = _make_unit(
        "Rogue Trader Entourage",
        "source",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_WARRANT_OF_TRADE_ABILITY],
    )
    has_redeploy, count, can_place_in_reserves = source.has_redeploy()
    assert has_redeploy
    assert int(count) >= 1
    assert bool(can_place_in_reserves)
    cache = dict(getattr(source, "_ability_cache", {}) or {})
    assert list(cache.get("redeploy_filters", []) or []) == ["IMPERIUM", "BATTLELINE"]
    assert bool(cache.get("redeploy_army_once_per_ability", False))


def test_warrant_of_trade_redeploy_selection_is_army_once_and_imperium_battleline_only():
    game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
    source_a = _make_unit(
        "Rogue Trader Entourage A",
        "source_a",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_WARRANT_OF_TRADE_ABILITY],
    )
    source_b = _make_unit(
        "Rogue Trader Entourage B",
        "source_b",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_WARRANT_OF_TRADE_ABILITY],
    )
    eligible = _make_unit(
        "Imperium Battleline Unit",
        "eligible",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["IMPERIUM", "AGENTS OF THE IMPERIUM"],
    )
    imperium_non_battleline = _make_unit(
        "Imperium Non-Battleline",
        "imperium_non_battleline",
        keywords=["INFANTRY"],
        faction_keywords=["IMPERIUM", "AGENTS OF THE IMPERIUM"],
    )
    battleline_non_imperium = _make_unit(
        "Battleline Non-Imperium",
        "battleline_non_imperium",
        keywords=["INFANTRY", "BATTLELINE"],
        faction_keywords=["AELDARI"],
    )
    enemy = _make_unit("Enemy Unit", "enemy", faction_keywords=["EN"])
    for unit in (
        source_a,
        source_b,
        eligible,
        imperium_non_battleline,
        battleline_non_imperium,
    ):
        ia_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _mark_deployed(
        source_a,
        source_b,
        eligible,
        imperium_non_battleline,
        battleline_non_imperium,
        enemy,
    )
    game.map.units = [
        source_a,
        source_b,
        eligible,
        imperium_non_battleline,
        battleline_non_imperium,
        enemy,
    ]
    game.rebuild_entity_registry()

    game.execute_redeploy_units_phase()

    state = dict(getattr(game, "_redeploy_state", {}) or {})
    player_queue = list((state.get("queues", {}) or {}).get(str(ia_player.id), []) or [])
    assert len(player_queue) == 1

    request = _find_warrant_request(game, player_id=str(ia_player.id))
    assert request is not None
    target_ids = {
        str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
        for opt in list(getattr(request, "options", []) or [])
        if str((dict(getattr(opt, "payload", {}) or {}).get("target_unit_id", "") or ""))
    }
    eligible_id = str(get_entity_id(eligible) or "")
    imperium_non_battleline_id = str(get_entity_id(imperium_non_battleline) or "")
    battleline_non_imperium_id = str(get_entity_id(battleline_non_imperium) or "")
    assert eligible_id in target_ids
    assert imperium_non_battleline_id not in target_ids
    assert battleline_non_imperium_id not in target_ids

    reserve_option_id = _find_option_id(
        request,
        target_unit_id=eligible_id,
        action="strategic_reserves",
    )
    assert bool(reserve_option_id)

    skip_option_id = _find_skip_option_id(request)
    assert bool(skip_option_id)
    result = resolve_decision_command(game, request, skip_option_id, player_id=ia_player.id)
    assert bool(getattr(result, "ok", False))
    assert _find_warrant_request(game, player_id=str(ia_player.id)) is None
