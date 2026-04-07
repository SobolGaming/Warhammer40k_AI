from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import (
    DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
    DECISION_CHOOSE_QUARRY,
    DECISION_CONFIRM_YES_NO,
    DECISION_DECLARE_SHOTS,
    DECISION_MOVE_UNIT,
)
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units import wargear as wargear_mod
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str, *, faction_id: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id=faction_id))


def _build_game() -> tuple[Game, Player, Player, Army, Army]:
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE

    enemy_army = Army.with_detachment("Enemy", "Other")
    enemy_army.faction_id = "ORK"
    gsc_army = Army.with_detachment("Genestealer Cults", "Other")
    gsc_army.faction_id = "GC"

    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    gsc_player = Player("GSC", control=PlayerControl.REMOTE, army=gsc_army)
    game.add_player(enemy_player)
    game.add_player(gsc_player)
    game.current_player_index = 0
    return game, enemy_player, gsc_player, enemy_army, gsc_army


def _deploy(unit: Unit, x: float, y: float, *, spacing: float = 1.5) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for idx, model in enumerate(list(getattr(unit, "models", []) or [])):
        model.set_location(float(x) + (float(idx) * float(spacing)), float(y), 0.0, 0.0)


def _find_request(game: Game, *, decision_type: str, kind: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("reactive_move_kind", "") or "").strip().lower() != str(kind or "").strip().lower():
            continue
        return request
    return None


def _find_request_for_ability(game: Game, *, decision_type: str, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != decision_type:
            continue
        ctx = dict(getattr(request, "context", {}) or {})
        if str(ctx.get("ability", "") or "").strip().lower() != str(ability or "").strip().lower():
            continue
        return request
    return None


def _find_request_by_decision_type(game: Game, decision_type: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") == decision_type:
            return request
    return None


def _aura_stub():
    return SimpleNamespace(
        hit=0,
        wound=0,
        reroll_hit_ones=False,
        reroll_wound_ones=False,
        reroll_hit_reasons=(),
        reroll_wound_reasons=(),
        target_toughness_delta=0,
        target_toughness_reasons=(),
    )


def _test_profile(name: str) -> WargearProfile:
    return WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name=name, is_ranged=lambda: True, is_melee=lambda: False),
    )


def test_hybrid_metamorphs_brood_surge_queues_fixed_6_move_without_hand_flamer() -> None:
    game, enemy_player, gsc_player, enemy_army, gsc_army = _build_game()

    attacker = _actual_unit("Boyz", faction_id="ORK")
    metamorphs = _actual_unit("Hybrid Metamorphs", faction_id="GC")

    enemy_army.add_unit(attacker)
    gsc_army.add_unit(metamorphs)
    _deploy(attacker, 0.0, 0.0, spacing=0.0)
    _deploy(metamorphs, 10.0, 0.0, spacing=0.0)
    game.map.units = [attacker, metamorphs]
    game.rebuild_entity_registry()

    rule = metamorphs.get_horde_move_rule(game=game)
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Brood Surge"
    assert int(rule.get("fixed_distance", 0) or 0) == 6

    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[metamorphs])
    metamorphs.models[0].wounds = 0
    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={metamorphs: 1})

    confirm_req = _find_request(game, decision_type=DECISION_CONFIRM_YES_NO, kind="horde_move")
    assert confirm_req is not None
    assert str(((confirm_req.context or {}).get("reactive_move_source", "") or "")).strip() == "Brood Surge"

    move_opt = next(opt for opt in list(confirm_req.options or []) if bool((opt.payload or {}).get("choice", False)))
    result = resolve_decision_command(game, confirm_req, move_opt.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    move_req = _find_request(game, decision_type=DECISION_MOVE_UNIT, kind="horde_move")
    assert move_req is not None
    assert str(((move_req.context or {}).get("movement_type", "") or "")).strip() == "horde_move"
    assert int(((move_req.context or {}).get("max_distance", 0) or 0)) == 6


def test_hybrid_metamorphs_brood_surge_uses_d6_when_hand_flamer_is_present() -> None:
    game, _enemy_player, _gsc_player, _enemy_army, gsc_army = _build_game()
    metamorphs = _actual_unit("Hybrid Metamorphs", faction_id="GC")
    gsc_army.add_unit(metamorphs)
    metamorphs.models[0].wargear.append(SimpleNamespace(name="Hand flamer"))
    metamorphs._ability_cache.pop("static_horde_move_rule", None)

    rule = metamorphs.get_horde_move_rule(game=game)
    assert isinstance(rule, dict)
    assert str(rule.get("source", "") or "") == "Brood Surge"
    assert int(rule.get("fixed_distance", 0) or 0) == 0


def test_jackal_alphus_priority_target_requires_cult_sniper_rifle_hit() -> None:
    game, _enemy_player, _gsc_player, enemy_army, gsc_army = _build_game()
    game.current_player_index = 1

    jackal_alphus = _actual_unit("Jackal Alphus", faction_id="GC")
    enemy_unit = _actual_unit("Boyz", faction_id="ORK")

    gsc_army.add_unit(jackal_alphus)
    enemy_army.add_unit(enemy_unit)
    _deploy(jackal_alphus, 0.0, 0.0, spacing=0.0)
    _deploy(enemy_unit, 10.0, 0.0, spacing=0.0)
    game.map.units = [jackal_alphus, enemy_unit]
    game.rebuild_entity_registry()

    specs = jackal_alphus.unit_post_shoot_keyword_hit_reroll_ones_specs()
    assert len(specs) == 1
    assert str(specs[0].get("source", "") or "") == "Priority Target"
    assert str(specs[0].get("keyword_phrase", "") or "") == "genestealer cults"
    assert str(specs[0].get("weapon_key", "") or "") == "cult sniper rifle"

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=jackal_alphus,
        hits_by_target={enemy_unit: 1},
        hit_models_by_target_weapon={
            enemy_unit: {
                "autopistol": [jackal_alphus.models[0]],
            }
        },
    )

    request = _find_request_for_ability(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="post_shoot_keyword_hit_reroll_ones",
    )
    assert request is None


def test_jackal_alphus_priority_target_marks_cult_sniper_rifle_target_for_hit_reroll_ones() -> None:
    game, _enemy_player, gsc_player, enemy_army, gsc_army = _build_game()
    game.current_player_index = 1

    jackal_alphus = _actual_unit("Jackal Alphus", faction_id="GC")
    ally = _actual_unit("Neophyte Hybrids", faction_id="GC")
    enemy_unit = _actual_unit("Boyz", faction_id="ORK")

    gsc_army.add_unit(jackal_alphus)
    gsc_army.add_unit(ally)
    enemy_army.add_unit(enemy_unit)
    _deploy(jackal_alphus, 0.0, 0.0, spacing=0.0)
    _deploy(ally, 2.0, 0.0)
    _deploy(enemy_unit, 10.0, 0.0)
    game.map.units = [jackal_alphus, ally, enemy_unit]
    game.rebuild_entity_registry()

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=jackal_alphus,
        hits_by_target={enemy_unit: 1},
        hit_models_by_target_weapon={
            enemy_unit: {
                "cult sniper rifle": [jackal_alphus.models[0]],
            }
        },
    )

    request = _find_request_for_ability(
        game,
        decision_type=DECISION_CHOOSE_QUARRY,
        ability="post_shoot_keyword_hit_reroll_ones",
    )
    assert request is not None
    assert str((request.context or {}).get("ability_name", "") or "") == "Priority Target"
    assert str((request.context or {}).get("weapon_key", "") or "") == "cult sniper rifle"

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    profile = _test_profile("Test Rifle")
    rolls = iter([1, 5])
    original_roll = wargear_mod.get_roll
    wargear_mod.get_roll = lambda _d: next(rolls)
    try:
        hit_result = profile._hit_target_with_tracking(
            enemy_unit,
            ally.models[0],
            {"_aura_attack_mods": _aura_stub()},
        )
    finally:
        wargear_mod.get_roll = original_roll

    assert int(hit_result.get("roll", 0) or 0) == 5
    assert int(hit_result.get("reroll_of_one", 0) or 0) == 1


def test_kelermorph_heroic_fusillade_targets_only_infantry_and_is_once_per_turn() -> None:
    game, _enemy_player, gsc_player, enemy_army, gsc_army = _build_game()
    game.current_player_index = 1

    kelermorph = _actual_unit("Kelermorph", faction_id="GC")
    enemy_infantry = _actual_unit("Boyz", faction_id="ORK")
    enemy_vehicle = _actual_unit("Trukk", faction_id="ORK")

    gsc_army.add_unit(kelermorph)
    enemy_army.add_unit(enemy_infantry)
    enemy_army.add_unit(enemy_vehicle)
    _deploy(kelermorph, 0.0, 0.0, spacing=0.0)
    _deploy(enemy_infantry, 10.0, 0.0)
    _deploy(enemy_vehicle, 12.0, 0.0, spacing=0.0)
    game.map.units = [kelermorph, enemy_infantry, enemy_vehicle]
    game.rebuild_entity_registry()

    battle_shock_turns: list[int] = []
    enemy_infantry.take_battle_shock_test = lambda turn: battle_shock_turns.append(int(turn))

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=kelermorph,
        hits_by_target={enemy_infantry: 1, enemy_vehicle: 1},
    )

    request = _find_request_by_decision_type(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert request is not None
    option_labels = [str(getattr(opt, "label", "") or "") for opt in list(request.options or [])]
    assert any(enemy_infantry.name in label for label in option_labels)
    assert not any(enemy_vehicle.name in label for label in option_labels)
    assert str((request.context or {}).get("army_usage_key", "") or "") == "HEROIC_FUSILLADE"

    result = resolve_decision_command(game, request, request.options[0].option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True
    assert battle_shock_turns == [1]

    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=kelermorph,
        hits_by_target={enemy_infantry: 1},
    )

    second_request = _find_request_by_decision_type(game, DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET)
    assert second_request is None


def test_kelermorph_hypersensory_abilities_queue_reactive_shoot_then_d6_move() -> None:
    game, enemy_player, gsc_player, enemy_army, gsc_army = _build_game()
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    game.current_player_index = 0

    enemy_unit = _actual_unit("Trukk", faction_id="ORK")
    kelermorph = _actual_unit("Kelermorph", faction_id="GC")

    enemy_army.add_unit(enemy_unit)
    gsc_army.add_unit(kelermorph)
    _deploy(enemy_unit, 0.0, 0.0, spacing=0.0)
    _deploy(kelermorph, 8.0, 0.0, spacing=0.0)
    game.map.units = [enemy_unit, kelermorph]
    game.rebuild_entity_registry()

    game._setup_reactive_can_shoot_target = lambda _unit, _target: True

    game.event_system.publish("unit_move_ended", unit=enemy_unit, action="move")

    shoot_request = _find_request_by_decision_type(game, DECISION_DECLARE_SHOTS)
    assert shoot_request is not None
    assert bool((shoot_request.context or {}).get("hypersensory_abilities_flow", False)) is True
    assert str((shoot_request.context or {}).get("force_target_unit_id", "") or "") == str(get_entity_id(enemy_unit) or "")

    ranged_wargear = next(
        wg
        for wg in list(kelermorph.models[0].wargear or [])
        if bool(getattr(wg, "is_ranged", lambda: False)())
    )
    model_id = str(get_entity_id(kelermorph.models[0]) or "")
    wargear_id = str(get_entity_id(ranged_wargear) or "")
    profile_name = next(iter((getattr(ranged_wargear, "profiles", {}) or {}).keys()))

    def _fake_execute(declarations, game_map, out_of_phase=False):
        game.event_system.publish(
            "unit_shooting_resolved",
            attacker_unit=kelermorph,
            hits_by_target={enemy_unit: 1},
        )
        return True

    kelermorph.execute_shooting_declarations = _fake_execute

    with patch("warhammer40k_ai.engine.game_mixins.shooting_fight_handlers_mixin.get_roll", return_value=4):
        result = resolve_decision_command(
            game,
            shoot_request,
            shoot_request.options[0].option_id,
            result_payload={
                "declarations": [
                    {
                        "wargear_id": wargear_id,
                        "profile_name": profile_name,
                        "target_unit_id": str(get_entity_id(enemy_unit) or ""),
                        "model_ids": [model_id],
                    }
                ]
            },
            player_id=gsc_player.id,
        )

    assert bool(getattr(result, "ok", False)) is True

    move_request = _find_request_by_decision_type(game, DECISION_MOVE_UNIT)
    assert move_request is not None
    assert str((move_request.context or {}).get("reactive_move_kind", "") or "") == "hypersensory_abilities"
    assert int((move_request.context or {}).get("max_distance", 0) or 0) == 4
