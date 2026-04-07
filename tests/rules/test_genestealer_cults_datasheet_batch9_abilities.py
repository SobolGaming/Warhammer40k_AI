from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE), players=[gsc_player, enemy_player])
    game.attacker_index = 0
    game.defender_index = 1
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _find_redeploy_request(game: Game, *, player_id: str, ability_name: str):
    for req in list(game.decision_queue.list() or []):
        if str(getattr(req, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        if str(getattr(req, "player_id", "") or "") != str(player_id):
            continue
        ctx = dict(getattr(req, "context", {}) or {})
        if str(ctx.get("ability_name", "") or "") != str(ability_name):
            continue
        return req
    return None


def test_primus_cult_demagogue_grants_led_unit_plus_one_to_hit() -> None:
    primus = _actual_unit("Primus", faction_id="GC")
    neophytes = _actual_unit("Neophyte Hybrids", faction_id="GC")

    neophytes.attached_leaders = [primus]
    primus.attached_to = neophytes

    mods = neophytes.get_leading_attack_roll_modifiers("ranged")
    assert int(mods.get("hit", 0) or 0) == 1
    assert any("Cult Demagogue" in str(reason or "") for reason in list(mods.get("hit_reasons", ()) or ()))


def test_primus_decoys_and_misdirection_queues_redeploy_request_with_strategic_reserves_option() -> None:
    game, gsc_player, _enemy_player, gsc_army, _enemy_army = _build_game()

    primus = _actual_unit("Primus", faction_id="GC")
    neophytes = _actual_unit("Neophyte Hybrids", faction_id="GC")
    acolytes = _actual_unit("Acolyte Hybrids With Autopistols", faction_id="GC")

    gsc_army.add_unit(primus)
    gsc_army.add_unit(neophytes)
    gsc_army.add_unit(acolytes)
    _deploy(primus, 0.0, 0.0, spacing=0.0)
    _deploy(neophytes, 6.0, 0.0)
    _deploy(acolytes, 12.0, 0.0)
    game.map.units = [primus, neophytes, acolytes]
    game.rebuild_entity_registry()

    has_redeploy, count, can_place_in_reserves = primus.has_redeploy()
    assert bool(has_redeploy) is True
    assert int(count or 0) == 3
    assert bool(can_place_in_reserves) is True

    game.execute_redeploy_units_phase()
    request = _find_redeploy_request(
        game,
        player_id=str(gsc_player.id),
        ability_name="Decoys and Misdirection",
    )
    assert request is not None

    neophyte_id = str(get_entity_id(neophytes) or "")
    options = [dict(getattr(opt, "payload", {}) or {}) for opt in list(request.options or [])]
    assert any(
        str(payload.get("target_unit_id", "") or "") == neophyte_id
        and str(payload.get("redeploy_action", "") or "").strip().lower() == "strategic_reserves"
        for payload in options
    )
