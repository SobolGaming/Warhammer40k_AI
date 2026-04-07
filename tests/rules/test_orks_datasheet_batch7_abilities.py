from __future__ import annotations

import types

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY, DECISION_MOVE_UNIT
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id="ORK"))


def _build_game() -> tuple[Game, Army, Army, Player, Player]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army.with_detachment("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    game.turn = 2
    return game, ork_army, enemy_army, ork_player, enemy_player


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _register_units(game: Game, *units: Unit) -> None:
    game.map.units = list(units)
    game.rebuild_entity_registry()


def _attach_weirdboy_to_boyz(ork_army: Army) -> tuple[Unit, Unit]:
    boyz = _actual_unit("Boyz")
    weirdboy = _actual_unit("Weirdboy")
    ork_army.add_unit(boyz)
    ork_army.add_unit(weirdboy)
    weirdboy.attach_to_unit(boyz)
    return boyz, weirdboy


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


def _find_move_request(game: Game, unit: Unit):
    root = unit.get_attached_unit_root() if hasattr(unit, "get_attached_unit_root") else unit
    root_id = str(get_entity_id(root) or "")
    return next(
        (
            req
            for req in list(game.decision_queue.list() or [])
            if str(getattr(req, "decision_type", "") or "") == DECISION_MOVE_UNIT
            and str((getattr(req, "context", {}) or {}).get("placement_kind", "") or "") == "normal_move_redeploy_9h"
            and str((getattr(req, "context", {}) or {}).get("unit_id", "") or "") == root_id
        ),
        None,
    )


def _source_option(request, source_unit: Unit):
    source_unit_id = str(get_entity_id(source_unit) or "")
    return next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("source_unit_id", "") or "") == source_unit_id
    )


def _attached_model_positions(root: Unit, start_x: float, start_y: float, *, spacing: float = 1.5) -> list[dict]:
    positions = []
    for idx, model in enumerate(list(root.get_attached_unit_models() or [])):
        positions.append(
            {
                "model_id": get_entity_id(model),
                "position": [float(start_x) + (float(idx) * float(spacing)), float(start_y), 0.0],
                "facing": 0.0,
            }
        )
    return positions


def test_da_jump_specs_parse_for_attached_weirdboy_root():
    ork_army = Army.with_detachment("Orks", "Other")
    ork_army.faction_id = "ORK"
    boyz, weirdboy = _attach_weirdboy_to_boyz(ork_army)

    specs = boyz.unit_movement_phase_end_da_jump_specs()

    assert len(specs) == 1
    spec = specs[0]
    assert str(spec.get("source", "") or "") == "Da Jump (Psychic)"
    assert str(spec.get("source_unit_id", "") or "") == str(get_entity_id(weirdboy) or "")
    assert str(spec.get("unit_id", "") or "") == str(get_entity_id(boyz) or "")
    assert int(spec.get("min_enemy_distance_horiz", 0) or 0) == 9
    assert int(spec.get("fail_on", 0) or 0) == 1
    assert str(spec.get("self_mortal_wounds_roll", "") or "") == "D6"
    assert str(spec.get("army_usage_key", "") or "") == "ORK_DA_JUMP"


def test_da_jump_phase_end_queues_choice_for_attached_weirdboy():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    boyz, weirdboy = _attach_weirdboy_to_boyz(ork_army)
    enemy = _actual_unit("Boyz")
    enemy_army.add_unit(enemy)
    _deploy(boyz, 0.0, 0.0)
    _deploy(weirdboy, 0.0, 0.0)
    _deploy(enemy, 30.0, 0.0)
    _register_units(game, boyz, weirdboy, enemy)

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "da_jump")

    assert request is not None
    assert str((request.context or {}).get("ability_name", "") or "") == "Da Jump (Psychic)"
    assert str((request.context or {}).get("army_usage_key", "") or "") == "ORK_DA_JUMP"
    assert str(get_entity_id(weirdboy) or "") in list((request.context or {}).get("candidate_source_unit_ids") or [])
    option_labels = [str(getattr(option, "label", "") or "") for option in list(request.options or [])]
    assert option_labels[0] == "None"
    assert any("Weirdboy" in label for label in option_labels[1:])

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    pending = [
        req
        for req in list(game.decision_queue.list() or [])
        if str((getattr(req, "context", {}) or {}).get("ability", "") or "") == "da_jump"
    ]
    assert len(pending) == 1


def test_da_jump_fail_roll_applies_self_mortal_wounds(monkeypatch):
    game, ork_army, _enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    boyz, weirdboy = _attach_weirdboy_to_boyz(ork_army)
    _deploy(boyz, 0.0, 0.0)
    _deploy(weirdboy, 0.0, 0.0)
    _register_units(game, boyz, weirdboy)

    applied: dict[str, object] = {}

    def _apply(self, target, amount, game_map=None, attacker_unit=None, attacker_model=None, damage_source=None):
        applied["target"] = target
        applied["amount"] = int(amount or 0)
        applied["attacker_unit"] = attacker_unit
        applied["attacker_model"] = attacker_model
        applied["damage_source"] = damage_source
        return 0

    boyz._apply_mortal_wounds_to_unit = types.MethodType(_apply, boyz)

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "da_jump")
    option = _source_option(request, weirdboy)
    rolls = iter([1, 4])
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: next(rolls))
    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(result, "ok", False)) is True
    assert applied["target"] is boyz
    assert int(applied["amount"] or 0) == 4
    assert applied["attacker_unit"] is boyz
    assert str(applied["damage_source"] or "") == "Da Jump (Psychic)"
    assert _find_move_request(game, boyz) is None
    assert bool(ork_player._ability_used_this_turn("ORK_DA_JUMP")) is True


def test_da_jump_success_queues_redeploy_move_and_repositions_attached_unit(monkeypatch):
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    boyz, weirdboy = _attach_weirdboy_to_boyz(ork_army)
    enemy = _actual_unit("Boyz")
    enemy_army.add_unit(enemy)
    _deploy(boyz, 0.0, 0.0)
    _deploy(weirdboy, 0.0, 0.0)
    _deploy(enemy, 60.0, 0.0)
    _register_units(game, boyz, weirdboy, enemy)
    game.map.is_within_boundary = lambda *_args, **_kwargs: True
    game.map.check_collision_with_obstacles = lambda *_args, **_kwargs: False

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "da_jump")
    option = _source_option(request, weirdboy)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: 2)
    choose_result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(choose_result, "ok", False)) is True
    move_request = _find_move_request(game, boyz)
    assert move_request is not None
    move_ctx = dict(getattr(move_request, "context", {}) or {})
    assert str(move_ctx.get("placement_kind", "") or "") == "normal_move_redeploy_9h"
    assert str(move_ctx.get("movement_type", "") or "") == "move"
    assert len(list(move_ctx.get("allowed_model_ids") or [])) == len(list(boyz.get_attached_unit_models() or []))

    model_positions = _attached_model_positions(boyz, 15.0, 0.0)
    move_result = resolve_decision_command(
        game,
        move_request,
        move_request.options[0].option_id,
        player_id=ork_player.id,
        result_payload={"model_positions": model_positions},
    )

    assert bool(getattr(move_result, "ok", False)) is True
    assert bool(getattr(boyz.round_state, "moved_this_round", False)) is True
    attached_models = list(boyz.get_attached_unit_models() or [])
    assert attached_models
    assert float(attached_models[0].get_location()[0]) >= 15.0
    assert float(attached_models[-1].get_location()[0]) >= 15.0
    assert bool(ork_player._ability_used_this_turn("ORK_DA_JUMP")) is True


def test_da_jump_validation_rejects_tampered_source_unit_payload():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    boyz, weirdboy = _attach_weirdboy_to_boyz(ork_army)
    enemy = _actual_unit("Boyz")
    enemy_army.add_unit(enemy)
    _deploy(boyz, 0.0, 0.0)
    _deploy(weirdboy, 0.0, 0.0)
    _deploy(enemy, 30.0, 0.0)
    _register_units(game, boyz, weirdboy, enemy)

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "da_jump")
    option = _source_option(request, weirdboy)
    option.payload["source_unit_id"] = str(get_entity_id(boyz) or "")
    result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(result, "ok", False)) is False
    assert any("ineligible source unit" in str(error or "").lower() for error in list(getattr(result, "errors", []) or []))


def test_da_jump_once_per_turn_army_limit_prevents_second_prompt_after_use(monkeypatch):
    game, ork_army, _enemy_army, ork_player, _enemy_player = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE

    boyz, weirdboy = _attach_weirdboy_to_boyz(ork_army)
    second_weirdboy = _actual_unit("Weirdboy")
    ork_army.add_unit(second_weirdboy)
    _deploy(boyz, 0.0, 0.0)
    _deploy(weirdboy, 0.0, 0.0)
    _deploy(second_weirdboy, 8.0, 0.0)
    _register_units(game, boyz, weirdboy, second_weirdboy)

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    request = _find_quarry_request(game, "da_jump")
    option = _source_option(request, weirdboy)
    monkeypatch.setattr("warhammer40k_ai.utility.dice.get_roll", lambda _expr: 2)
    choose_result = resolve_decision_command(game, request, option.option_id, player_id=ork_player.id)

    assert bool(getattr(choose_result, "ok", False)) is True
    assert bool(ork_player._ability_used_this_turn("ORK_DA_JUMP")) is True

    game._on_phase_end_orks_da_jump(player=ork_player, phase=game.phase)
    assert _find_quarry_request(game, "da_jump") is None
