from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str) -> Unit:
    unit = Unit(_WAHA.get_datasheet(name, faction_id="SM"))
    unit.deployed = True
    unit.reserve_status = "deployed"
    return unit


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1
    game.phase = BattleRoundPhases.SHOOTING_PHASE
    sm_army = Army("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", detachment_type="Other")
    enemy_army.faction_id = "EN"
    sm_player = Player("Space Marines", PlayerControl.REMOTE, army=sm_army)
    enemy_player = Player("Enemy", PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)
    game.current_player_index = 0
    return game, sm_army, enemy_army, sm_player


def _set_unit_position(unit: Unit, x: float, y: float) -> None:
    for index, model in enumerate(list(unit.models or [])):
        model.set_location(x + (index * 0.1), y, 0.0, 0.0)


def _profile(unit: Unit, wargear_name: str):
    for wargear in list(unit.models[0].wargear or []):
        if str(getattr(wargear, "name", "") or "") == wargear_name:
            return wargear.profiles["default"]
    raise AssertionError(f"Profile for {wargear_name!r} not found")


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


def test_hammerstrike_queues_and_applies_post_shoot_no_cover() -> None:
    game, sm_army, enemy_army, sm_player = _build_game()
    hammerstrike = _actual_unit("Storm Speeder Hammerstrike")
    target = _actual_unit("Scout Squad")
    other_target = _actual_unit("Intercessor Squad")
    sm_army.add_unit(hammerstrike)
    enemy_army.add_unit(target)
    enemy_army.add_unit(other_target)

    _set_unit_position(hammerstrike, 0.0, 0.0)
    _set_unit_position(target, 12.0, 0.0)
    _set_unit_position(other_target, 18.0, 0.0)
    game.map.units = [hammerstrike, target, other_target]

    specs = hammerstrike.unit_post_shoot_no_cover_specs()
    assert len(specs) == 1
    assert bool(specs[0].get("any_weapon", False)) is True
    assert str(specs[0].get("duration", "") or "") == "phase_end"
    assert str(specs[0].get("source", "") or "") == "Hammerstrike"

    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=hammerstrike,
        hits_by_target={target: 1},
        hit_models_by_target_weapon={},
    )

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert str((request.context or {}).get("ability", "") or "") == "post_shoot_no_cover"
    assert str((request.context or {}).get("ability_name", "") or "") == "Hammerstrike"

    resolve_decision_command(game, request, request.options[0].option_id, player_id=sm_player.id)

    target_sr = getattr(target, "special_rules", {}) or {}
    assert bool(target_sr.get("post_shoot_no_cover_active", False)) is True
    assert str(target_sr.get("post_shoot_no_cover_expires_phase", "") or "") == "SHOOTING_PHASE"
    assert "Hammerstrike" in str(target_sr.get("post_shoot_no_cover_source", "") or "")

    profile = _profile(hammerstrike, "Hammerstrike missile launcher")
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        target,
        hammerstrike.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
    )
    assert bool(attack_instance.get("ignores_cover", False)) is True
