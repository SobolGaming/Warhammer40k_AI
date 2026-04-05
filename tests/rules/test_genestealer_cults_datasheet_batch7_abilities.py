from __future__ import annotations

from warhammer40k_ai.engine.decision_kinds import DECISION_PICK_POINT
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
    game.phase = BattleRoundPhases.COMMAND_PHASE

    gsc_army = Army("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "ORK"

    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(gsc_player)
    game.add_player(enemy_player)
    return game, gsc_player, enemy_player, gsc_army, enemy_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _find_request(game: Game, *, decision_type: str, ability: str):
    ability_key = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != ability_key:
            continue
        return request
    return None


def _option_with_marker(request):
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        marker_id = str(payload.get("marker_id", "") or "").strip()
        if marker_id:
            return option
    return None


def _option_for_action(request, action: str):
    action_key = str(action or "").strip().lower()
    for option in list(getattr(request, "options", []) or []):
        payload = dict(getattr(option, "payload", {}) or {})
        if str(payload.get("action", "") or "").strip().lower() == action_key:
            return option
    return None


def test_nexos_cult_infiltration_moves_marker_up_to_six_and_refreshes_on_next_players_command_phase() -> None:
    game, gsc_player, enemy_player, gsc_army, enemy_army = _build_game()

    nexos = _actual_unit("Nexos", faction_id="GC")
    enemy = _actual_unit("Boyz", faction_id="ORK")
    gsc_army.add_unit(nexos)
    enemy_army.add_unit(enemy)
    _deploy(nexos, 0.0, 0.0, spacing=0.0)
    _deploy(enemy, 40.0, 0.0)
    _register_units(game, nexos, enemy)

    manager = gsc_army.cult_ambush
    assert manager is not None
    marker = manager.place_marker_at(game, 10.0, 0.0)
    assert marker is not None

    game.current_player_index = 1
    game._on_phase_start_cult_infiltration(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)

    request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="cult_infiltration_marker_relocation",
    )
    assert request is not None
    assert str(getattr(request, "player_id", "") or "") == str(gsc_player.id)

    marker_option = _option_with_marker(request)
    assert marker_option is not None

    invalid = resolve_decision_command(
        game,
        request,
        marker_option.option_id,
        result_payload={"point": [17.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(invalid, "ok", False)) is False
    assert "up to 6" in str((getattr(invalid, "errors", ()) or ("",))[0]).lower()
    assert float(getattr(marker, "x", -1.0)) == 10.0

    valid = resolve_decision_command(
        game,
        request,
        marker_option.option_id,
        result_payload={"point": [13.0, 0.0]},
        player_id=gsc_player.id,
    )
    assert bool(getattr(valid, "ok", False)) is True
    assert float(getattr(marker, "x", -1.0)) == 13.0
    assert float(getattr(marker, "y", -1.0)) == 0.0
    assert str(getattr(marker, "last_moved_turn_owner_id", "") or "") == str(enemy_player.id)
    assert int(getattr(marker, "last_moved_turn", 0) or 0) == 1

    game._on_phase_start_cult_infiltration(player=enemy_player, phase=BattleRoundPhases.COMMAND_PHASE)
    assert (
        _find_request(
            game,
            decision_type=DECISION_PICK_POINT,
            ability="cult_infiltration_marker_relocation",
        )
        is None
    )

    game.current_player_index = 0
    game._on_phase_start_cult_infiltration(player=gsc_player, phase=BattleRoundPhases.COMMAND_PHASE)
    next_request = _find_request(
        game,
        decision_type=DECISION_PICK_POINT,
        ability="cult_infiltration_marker_relocation",
    )
    assert next_request is not None

    skip_option = _option_for_action(next_request, "skip")
    assert skip_option is not None
    skipped = resolve_decision_command(game, next_request, skip_option.option_id, player_id=gsc_player.id)
    assert bool(getattr(skipped, "ok", False)) is True
