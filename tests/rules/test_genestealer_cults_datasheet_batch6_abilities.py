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


def _find_quarry_request(game: Game, ability: str):
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
            and str((getattr(req, "context", {}) or {}).get("ability", "") or "") == ability
        ),
        None,
    )


def test_gc_manticore_furious_barrage_prompts_for_hit_non_vehicle_target_and_clears_next_turn() -> None:
    game, gsc_player, _enemy_player, gsc_army, enemy_army = _build_game()

    manticore = _actual_unit("Manticore", faction_id="GC")
    valid_target = _actual_unit("Boyz", faction_id="ORK")
    vehicle_target = _actual_unit("Trukk", faction_id="ORK")
    wrong_weapon_target = _actual_unit("Kommandos", faction_id="ORK")

    gsc_army.add_unit(manticore)
    enemy_army.add_unit(valid_target)
    enemy_army.add_unit(vehicle_target)
    enemy_army.add_unit(wrong_weapon_target)
    _deploy(manticore, 0.0, 0.0, spacing=0.0)
    _deploy(valid_target, 10.0, 0.0)
    _deploy(vehicle_target, 12.0, 0.0, spacing=0.0)
    _deploy(wrong_weapon_target, 14.0, 0.0)
    game.map.units = [manticore, valid_target, vehicle_target, wrong_weapon_target]
    game.rebuild_entity_registry()

    storm_eagle_rockets_key = manticore._normalize_keyword_phrase("Storm Eagle Rockets") or "storm eagle rockets"
    heavy_stub_key = manticore._normalize_keyword_phrase("Heavy Stubber") or "heavy stubber"

    game._on_unit_shooting_resolved_post_shoot_staggered_oc(
        attacker_unit=manticore,
        hits_by_target={
            valid_target: 2,
            vehicle_target: 1,
            wrong_weapon_target: 1,
        },
        hit_models_by_target_weapon={
            valid_target: {storm_eagle_rockets_key: [manticore.models[0]]},
            vehicle_target: {storm_eagle_rockets_key: [manticore.models[0]]},
            wrong_weapon_target: {heavy_stub_key: [manticore.models[0]]},
        },
    )

    request = _find_quarry_request(game, "post_shoot_staggered_oc")
    assert request is not None
    option_target_ids = {
        str((getattr(option, "payload", {}) or {}).get("target_unit_id", "") or "")
        for option in list(request.options or [])
    }
    assert option_target_ids == {str(get_entity_id(valid_target) or "")}

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    target_model = valid_target.models[0]
    assert int(Unit.get_effective_model_characteristic(valid_target, target_model, "objective_control")) == 1
    assert bool(valid_target.special_rules.get("post_shoot_staggered_oc_active")) is True
    assert int(valid_target.special_rules.get("post_shoot_staggered_oc_turn", 0) or 0) == 2

    game.current_player_index = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    assert int(Unit.get_effective_model_characteristic(valid_target, target_model, "objective_control")) == 1

    game.current_player_index = 0
    game.turn = 3
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    game._on_phase_start_post_shoot_duration_cleanup(player=gsc_player, phase=game.phase)

    assert bool(valid_target.special_rules.get("post_shoot_staggered_oc_active")) is False
    assert int(Unit.get_effective_model_characteristic(valid_target, target_model, "objective_control")) == 2
