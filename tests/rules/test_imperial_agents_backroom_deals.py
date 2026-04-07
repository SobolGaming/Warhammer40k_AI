from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


_BACKROOM_DEALS_ABILITY = {
    "name": "Backroom Deals",
    "description": (
        "If your army contains one or more units with this ability, during the Declare Battle Formations step, "
        "select one of those units. While the selected unit is leading a unit, models in that unit have the "
        "Infiltrators ability."
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
        attached_to=None,
    ):
        self.id = str(datasheet_id)
        self.name = name
        self.faction_data = {"name": "Imperial Agents"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or ["AGENTS OF THE IMPERIUM"])
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
        self.attached_to = list(attached_to or [])
        self.attached_to_names = []


def _make_unit(
    name: str,
    datasheet_id: str,
    *,
    keywords=None,
    faction_keywords=None,
    abilities=None,
    attached_to=None,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            datasheet_id,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            attached_to=attached_to,
        )
    )


def _mark_deployed(*units: Unit) -> None:
    for unit in units:
        unit.deployed = True
        unit.reserve_status = "deployed"


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ia_army = Army.with_detachment("Imperial Agents", "Imperialis Fleet")
    ia_army.faction_id = "AOI"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ia_player = Player("Imperial Agents", control=PlayerControl.REMOTE, army=ia_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ia_player)
    game.add_player(enemy_player)
    return game, ia_player, enemy_player, ia_army, enemy_army


def _find_backroom_request(game: Game):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != "army_selected_leading_infiltrators_declare":
            continue
        return req
    return None


def _option_for_unit(request, unit: Unit):
    target_id = str(get_entity_id(unit) or "")
    for opt in list(getattr(request, "options", []) or []):
        payload = dict(getattr(opt, "payload", {}) or {})
        if str(payload.get("selected_unit_id", "") or "") == target_id:
            return opt
    return None


def test_backroom_deals_queues_declare_battle_formations_selection_request():
    game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
    bodyguard_a = _make_unit("Voidsmen-at-arms A", "bodyguard_a", keywords=["INFANTRY"])
    bodyguard_b = _make_unit("Voidsmen-at-arms B", "bodyguard_b", keywords=["INFANTRY"])
    source_a = _make_unit(
        "Rogue Trader Entourage A",
        "source_a",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_BACKROOM_DEALS_ABILITY],
        attached_to=[bodyguard_a.get_datasheet_id()],
    )
    source_b = _make_unit(
        "Rogue Trader Entourage B",
        "source_b",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_BACKROOM_DEALS_ABILITY],
        attached_to=[bodyguard_b.get_datasheet_id()],
    )
    enemy = _make_unit("Enemy Unit", "enemy", faction_keywords=["EN"])
    for unit in (bodyguard_a, bodyguard_b, source_a, source_b):
        ia_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _mark_deployed(bodyguard_a, bodyguard_b, source_a, source_b, enemy)
    game.map.units = [bodyguard_a, bodyguard_b, source_a, source_b, enemy]
    game.rebuild_entity_registry()

    game.execute_declare_battle_formations_phase()

    request = _find_backroom_request(game)
    assert request is not None
    assert str((request.context or {}).get("ability_name", "") or "") == "Backroom Deals"
    assert str(request.player_id or "") == str(ia_player.id or "")
    candidate_ids = {str(v or "") for v in list((request.context or {}).get("candidate_unit_ids", []) or []) if str(v or "")}
    assert candidate_ids == {
        str(get_entity_id(source_a) or ""),
        str(get_entity_id(source_b) or ""),
    }


def test_backroom_deals_selected_unit_grants_infiltrators_only_while_leading():
    game, ia_player, _enemy_player, ia_army, enemy_army = _build_game()
    bodyguard_a = _make_unit("Voidsmen-at-arms A", "bodyguard_a", keywords=["INFANTRY"])
    bodyguard_b = _make_unit("Voidsmen-at-arms B", "bodyguard_b", keywords=["INFANTRY"])
    source_a = _make_unit(
        "Rogue Trader Entourage A",
        "source_a",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_BACKROOM_DEALS_ABILITY],
        attached_to=[bodyguard_a.get_datasheet_id()],
    )
    source_b = _make_unit(
        "Rogue Trader Entourage B",
        "source_b",
        keywords=["CHARACTER", "INFANTRY"],
        abilities=[_BACKROOM_DEALS_ABILITY],
        attached_to=[bodyguard_b.get_datasheet_id()],
    )
    enemy = _make_unit("Enemy Unit", "enemy", faction_keywords=["EN"])
    for unit in (bodyguard_a, bodyguard_b, source_a, source_b):
        ia_army.add_unit(unit)
    enemy_army.add_unit(enemy)
    _mark_deployed(bodyguard_a, bodyguard_b, source_a, source_b, enemy)
    game.map.units = [bodyguard_a, bodyguard_b, source_a, source_b, enemy]
    game.rebuild_entity_registry()

    game.execute_declare_battle_formations_phase()
    request = _find_backroom_request(game)
    assert request is not None

    pick_source_a = _option_for_unit(request, source_a)
    assert pick_source_a is not None
    result = resolve_decision_command(game, request, pick_source_a.option_id, player_id=ia_player.id)
    assert bool(getattr(result, "ok", False))

    assert source_a.has_infiltrate() is False
    assert source_b.has_infiltrate() is False
    assert bodyguard_a.has_infiltrate() is False
    assert bodyguard_b.has_infiltrate() is False
    source_a_sr = source_a.special_rules if isinstance(source_a.special_rules, dict) else {}
    source_b_sr = source_b.special_rules if isinstance(source_b.special_rules, dict) else {}
    assert bool(source_a_sr.get("declare_battle_formations_selected_leading_infiltrators", False))
    assert not bool(source_b_sr.get("declare_battle_formations_selected_leading_infiltrators", False))

    source_a.attach_to_unit(bodyguard_a)
    source_b.attach_to_unit(bodyguard_b)

    assert source_a.has_infiltrate() is True
    assert bodyguard_a.has_infiltrate() is True
    assert source_b.has_infiltrate() is False
    assert bodyguard_b.has_infiltrate() is False

    source_a.detach_from_unit()
    assert source_a.has_infiltrate() is False
    assert bodyguard_a.has_infiltrate() is False
