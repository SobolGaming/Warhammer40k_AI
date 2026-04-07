from __future__ import annotations

from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CONFIRM_YES_NO
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    game.current_player_index = 1
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _find_request(game: Game, decision_type: str, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == decision_type
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def test_gc_primaris_psyker_psychic_barrier_grants_unit_invulnerable_save() -> None:
    game, gsc_player, enemy_player, gsc_army, enemy_army = _build_game()

    psyker = _actual_unit("Primaris Psyker", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")

    gsc_army.add_unit(psyker)
    enemy_army.add_unit(enemy)
    _deploy(psyker, 0.0, 0.0, spacing=0.0)
    _deploy(enemy, 12.0, 0.0)
    game.map.units = [psyker, enemy]
    game.rebuild_entity_registry()

    game._on_phase_start_astra_militarum_psychic_barrier(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    request = _find_request(game, DECISION_CONFIRM_YES_NO, "psychic_barrier")
    assert request is not None

    use_option = next(
        opt
        for opt in list(request.options or [])
        if bool((getattr(opt, "payload", {}) or {}).get("choice", False)) is True
    )
    with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
        result = resolve_decision_command(game, request, use_option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    invuln, _source = psyker.models[0].get_temporary_invulnerable_save()
    assert int(invuln or 0) == 4
