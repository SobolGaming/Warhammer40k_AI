from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
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


def _find_disrupt_request(game: Game):
    for request in list(game.decision_queue.list() or []):
        if str((request.context or {}).get("ability", "") or "") == "opponent_shooting_phase_disrupt":
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


def _ranged_profile(name: str) -> WargearProfile:
    return WargearProfile(
        "default",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=SimpleNamespace(name=name, is_ranged=lambda: True, is_melee=lambda: False),
    )


def test_magus_mind_control_targets_nonvisible_enemy_and_applies_hit_and_wound_penalties_on_six() -> None:
    game, enemy_player, gsc_player, enemy_army, gsc_army = _build_game()

    magus = _actual_unit("Magus", faction_id="GC")
    enemy_unit = _actual_unit("Boyz", faction_id="ORK")
    victim = _actual_unit("Neophyte Hybrids", faction_id="GC")

    gsc_army.add_unit(magus)
    gsc_army.add_unit(victim)
    enemy_army.add_unit(enemy_unit)
    _deploy(magus, 0.0, 0.0, spacing=0.0)
    _deploy(enemy_unit, 16.0, 0.0, spacing=0.0)
    _deploy(victim, 8.0, 0.0)
    game.map.units = [magus, enemy_unit, victim]
    game.rebuild_entity_registry()

    magus._has_line_of_sight_to_target = lambda *_args, **_kwargs: False

    game._on_phase_start_opponent_shooting_phase_disrupt(
        player=enemy_player,
        phase=BattleRoundPhases.SHOOTING_PHASE,
    )
    request = _find_disrupt_request(game)
    assert request is not None

    target_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_unit) or "")
    )
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6]):
        result = resolve_decision_command(game, request, target_option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    enemy_sr = enemy_unit.special_rules
    assert bool(enemy_sr.get("shooting_phase_hit_penalty_active", False)) is True
    assert bool(enemy_sr.get("shooting_phase_wound_penalty_active", False)) is True

    profile = _ranged_profile("Shoota")
    hit_result = profile._hit_target_with_tracking(
        victim,
        enemy_unit.models[0],
        {"_aura_attack_mods": _aura_stub()},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_result = profile._wound_target_with_tracking(
        victim,
        enemy_unit.models[0],
        {"distance_to_target": 12.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )

    hit_mods = [str(value or "") for value in list(hit_result.get("modifiers", []) or [])]
    wound_mods = [str(value or "") for value in list(wound_result.get("modifiers", []) or [])]
    assert any("Mind Control" in mod for mod in hit_mods)
    assert any("Mind Control" in mod for mod in wound_mods)

    game._on_phase_end_shooting_phase_disrupt_cleanup(player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    assert not bool(enemy_unit.special_rules.get("shooting_phase_hit_penalty_active", False))
    assert not bool(enemy_unit.special_rules.get("shooting_phase_wound_penalty_active", False))


def test_magus_psychic_familiar_extends_mind_control_range_once_per_battle() -> None:
    game, enemy_player, gsc_player, enemy_army, gsc_army = _build_game()

    magus = _actual_unit("Magus", faction_id="GC")
    enemy_unit = _actual_unit("Trukk", faction_id="ORK")

    gsc_army.add_unit(magus)
    enemy_army.add_unit(enemy_unit)
    _deploy(magus, 0.0, 0.0, spacing=0.0)
    _deploy(enemy_unit, 23.0, 0.0, spacing=0.0)
    game.map.units = [magus, enemy_unit]
    game.rebuild_entity_registry()

    magus._has_line_of_sight_to_target = lambda *_args, **_kwargs: False

    game._on_phase_start_opponent_shooting_phase_disrupt(
        player=enemy_player,
        phase=BattleRoundPhases.SHOOTING_PHASE,
    )
    request = _find_disrupt_request(game)
    assert request is not None

    familiar_option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy_unit) or "")
    )
    assert bool((familiar_option.payload or {}).get("use_extended_range", False)) is True
    assert str((familiar_option.payload or {}).get("extended_range_source", "") or "") == "Psychic Familiar"

    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[2]):
        result = resolve_decision_command(game, request, familiar_option.option_id, player_id=gsc_player.id)
    assert bool(getattr(result, "ok", False)) is True

    sr = magus.special_rules
    usage_map = dict(sr.get("opponent_shooting_phase_disrupt_extended_range_used", {}) or {})
    used_ids = {
        str(value or "").strip()
        for values in list(usage_map.values())
        for value in list(values or [])
        if str(value or "").strip()
    }
    assert str(get_entity_id(magus.models[0]) or "") in used_ids

    while game.decision_queue.pop() is not None:
        pass
    game.turn = 2
    game._on_phase_start_opponent_shooting_phase_disrupt(
        player=enemy_player,
        phase=BattleRoundPhases.SHOOTING_PHASE,
    )
    second_request = _find_disrupt_request(game)
    assert second_request is None
