from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 2
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _find_request(game: Game, *, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def test_gc_taurox_prime_transport_support_applies_hit_rerolls_to_disembarked_models() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    taurox = _actual_unit("Taurox Prime", faction_id="GC")
    passenger = _actual_unit("Neophyte Hybrids", faction_id="GC")
    enemy = _actual_unit("Warboss", faction_id="ORK")

    gsc_army.add_unit(taurox)
    gsc_army.add_unit(passenger)
    enemy_army.add_unit(enemy)
    _deploy(taurox, 0.0, 0.0, spacing=0.0)
    _deploy(passenger, 3.0, 0.0)
    _deploy(enemy, 10.0, 0.0, spacing=0.0)
    game.map.units = [taurox, passenger, enemy]
    game.rebuild_entity_registry()

    passenger.round_state.disembarked_from_transport_id = str(get_entity_id(taurox) or "")
    game._on_unit_shooting_resolved_post_shoot_disembark_hit_reroll(
        attacker_unit=taurox,
        hits_by_target={enemy: 1},
        hit_models_by_target={enemy: {taurox.models[0]}},
    )

    req = _find_request(game, ability="post_shoot_disembark_hit_reroll")
    assert req is not None
    target_option = next(
        opt
        for opt in list(req.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, req, target_option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    mods = passenger.get_model_hit_reroll_modifiers(passenger.models[0], attack_type="ranged", target=enemy)
    assert bool(mods.get("reroll_hit_full", False)) is True
    reasons = " ".join(str(value) for value in list(mods.get("reroll_hit_full_reasons", ()) or []))
    assert "Transport Support" in reasons
