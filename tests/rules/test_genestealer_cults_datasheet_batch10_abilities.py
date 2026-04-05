from __future__ import annotations

from unittest.mock import Mock, patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
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


def _source_option(request, source_unit: Unit):
    source_unit_id = str(get_entity_id(source_unit) or "")
    return next(
        opt
        for opt in list(getattr(request, "options", []) or [])
        if str((getattr(opt, "payload", {}) or {}).get("source_unit_id", "") or "") == source_unit_id
    )


def test_reductus_saboteur_planted_explosives_groups_sources_and_enforces_armywide_round_cap() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    saboteur_a = _actual_unit("Reductus Saboteur", faction_id="GC")
    saboteur_b = _actual_unit("Reductus Saboteur", faction_id="GC")
    enemy = _actual_unit("Warboss", faction_id="ORK")

    saboteur_a._apply_mortal_wounds_to_unit = Mock()
    saboteur_b._apply_mortal_wounds_to_unit = Mock()

    gsc_army.add_unit(saboteur_a)
    gsc_army.add_unit(saboteur_b)
    enemy_army.add_unit(enemy)
    _deploy(saboteur_a, 0.0, 0.0, spacing=0.0)
    _deploy(saboteur_b, 3.0, 0.0, spacing=0.0)
    _deploy(enemy, 8.0, 0.0, spacing=0.0)
    game.map.units = [saboteur_a, saboteur_b, enemy]
    game.rebuild_entity_registry()

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")

    request = _find_request(game, ability="enemy_move_range_mortal_threshold")
    assert request is not None
    ctx = dict(getattr(request, "context", {}) or {})
    assert str(ctx.get("ability_name", "") or "") == "Planted Explosives"
    assert str(ctx.get("army_usage_scope", "") or "") == "battle_round"
    assert len(list(ctx.get("candidate_source_unit_ids", []) or [])) == 2
    assert len(list(ctx.get("candidate_source_model_ids", []) or [])) == 2
    assert len(list(getattr(request, "options", []) or [])) == 3

    option = _source_option(request, saboteur_a)

    def _roll(expr: str):
        expr_key = str(expr or "").strip().upper()
        if expr_key == "D6":
            return 2
        if expr_key == "D3+3":
            return 5
        raise AssertionError(f"Unexpected roll expression: {expr_key}")

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=_roll):
        result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)

    assert bool(getattr(result, "ok", False)) is True
    saboteur_a._apply_mortal_wounds_to_unit.assert_called_once()
    assert saboteur_a._apply_mortal_wounds_to_unit.call_args.args[0] is enemy
    assert int(saboteur_a._apply_mortal_wounds_to_unit.call_args.args[1] or 0) == 5
    saboteur_b._apply_mortal_wounds_to_unit.assert_not_called()
    assert saboteur_a.models[0].has_used_once_per_battle("enemy_move_range_mortal_threshold:planted explosives")

    game.event_system.publish("unit_move_ended", unit=enemy, action="advance")
    assert _find_request(game, ability="enemy_move_range_mortal_threshold") is None


def test_reductus_saboteur_planted_explosives_requires_target_to_still_be_in_range() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    saboteur = _actual_unit("Reductus Saboteur", faction_id="GC")
    enemy = _actual_unit("Warboss", faction_id="ORK")

    gsc_army.add_unit(saboteur)
    enemy_army.add_unit(enemy)
    _deploy(saboteur, 0.0, 0.0, spacing=0.0)
    _deploy(enemy, 8.0, 0.0, spacing=0.0)
    game.map.units = [saboteur, enemy]
    game.rebuild_entity_registry()

    game.event_system.publish("unit_move_ended", unit=enemy, action="move")
    request = _find_request(game, ability="enemy_move_range_mortal_threshold")
    assert request is not None

    enemy.models[0].set_location(20.0, 0.0, 0.0, 0.0)
    option = _source_option(request, saboteur)
    result = resolve_decision_command(game, request, option.option_id, player_id=gsc_player.id)

    assert not bool(getattr(result, "ok", False))
    assert any("within range" in str(err).lower() for err in list(getattr(result, "errors", []) or []))
