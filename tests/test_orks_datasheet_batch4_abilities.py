from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.utility.aura_effects import get_aura_weapon_keyword_bonuses
from warhammer40k_ai.utility.calcs import MovementType, get_validation_rules
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.waha_helper.waha_helper import WahaHelper


_WAHA = WahaHelper(data_dir="wahapedia_data")


def _actual_unit(name: str) -> Unit:
    return Unit(_WAHA.get_datasheet(name, faction_id="ORK"))


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    ork_army = Army("Orks", "Other")
    ork_army.faction_id = "ORK"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"
    ork_player = Player("Orks", control=PlayerControl.REMOTE, army=ork_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ork_player)
    game.add_player(enemy_player)
    game.turn = 1
    game.current_player_index = 0
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


def _mark_waaagh_active(army: Army, player: Player) -> None:
    army.waaagh.active = True
    army.waaagh.used_this_battle = True
    army.waaagh.called_turn = 1
    army.waaagh.called_player = player


def _find_choose_quarry_request(game: Game, *, ability: str):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != DECISION_CHOOSE_QUARRY:
            continue
        context = dict(getattr(request, "context", {}) or {})
        if str(context.get("ability", "") or "") == str(ability or ""):
            return request
    return None


def test_gorkanaut_big_an_stompy_and_clankin_forward_apply():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    gorkanaut = _actual_unit("Gorkanaut")
    target = _actual_unit("Boyz")
    ork_army.add_unit(gorkanaut)
    enemy_army.add_unit(target)
    _deploy(gorkanaut, 0.0, 0.0)
    _deploy(target, 2.0, 0.0)
    _register_units(game, gorkanaut, target)

    klaw = next(wg for wg in gorkanaut.models[0].wargear if wg.name == "Klaw of Gork")
    profile = klaw.profiles["strike"]

    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2]):
        no_waaagh = profile._hit_target_with_tracking(
            target,
            gorkanaut.models[0],
            {"attacker_model": gorkanaut.models[0], "target_unit": target},
        )
    assert bool(no_waaagh.get("hit", False)) is False

    _mark_waaagh_active(ork_army, ork_player)
    with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[2]):
        with_waaagh = profile._hit_target_with_tracking(
            target,
            gorkanaut.models[0],
            {"attacker_model": gorkanaut.models[0], "target_unit": target},
        )
    assert bool(with_waaagh.get("hit", False)) is True
    assert "+1 to hit from Big an' Stompy" in list(with_waaagh.get("modifiers", []) or [])

    move_rules = get_validation_rules(MovementType.MOVE, moving_unit=gorkanaut)
    assert bool(move_rules.get("can_move_through_enemy_models")) is True
    assert bool(move_rules.get("ignore_enemy_models_blocking")) is True
    assert bool(move_rules.get("block_monster_vehicle_models")) is True
    assert float(move_rules.get("free_climb_height_inches", 0.0) or 0.0) == 4.0


def test_gretchin_runtherd_toughness_override_and_thievin_scavengers_cp_gain():
    gretchin = _actual_unit("Gretchin")
    assert int(gretchin.toughness) == 2
    for model in list(gretchin.models[1:] or []):
        model.wounds = 0
    assert int(gretchin.toughness) == 5

    game, ork_army, _enemy_army, ork_player, _enemy_player = _build_game()
    gretchin = _actual_unit("Gretchin")
    ork_army.add_unit(gretchin)
    _deploy(gretchin, 0.0, 0.0)
    _register_units(game, gretchin)

    objective_location = SimpleNamespace(id="OBJ-1", controlling_player=ork_player, removed=False)
    objective = SimpleNamespace(name="Center Objective", location=objective_location)
    game.map.objectives = [objective]
    gretchin.is_within_objective_range = lambda _location: True
    ork_player.command_points = 0

    with patch("warhammer40k_ai.engine.game_mixins.phase_handlers_mixin.get_roll", side_effect=[4]):
        game._on_phase_start_orks_thievin_scavengers(
            player=ork_player,
            phase=BattleRoundPhases.MOVEMENT_PHASE,
        )

    assert int(ork_player.command_points) == 1


def test_hunta_rig_on_da_hunt_adds_embarked_models_to_butcha_boyz_with_cap():
    hunta_rig = _actual_unit("Hunta Rig")
    hunta_rig.transport_passengers = [_actual_unit("Boyz"), _actual_unit("Boyz")]
    target = _actual_unit("Boyz")

    butcha_boyz = next(wg for wg in hunta_rig.models[0].wargear if wg.name == "Butcha boyz")
    profile = butcha_boyz.profiles["default"]
    attack_count = profile.preview_attack_count(target, hunta_rig.models[0])

    assert int(attack_count.num_attacks) == 10
    assert "On Da Hunt +6A (Butcha boyz)" in list(attack_count.special_modifiers or [])


def test_ghazghkull_prophet_of_da_great_waaagh_grants_leading_hit_wound_and_crit_bonus():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    ghazghkull = _actual_unit("Ghazghkull Thraka")
    bodyguard = _actual_unit("Boyz")
    target = _actual_unit("Boyz")
    ork_army.add_unit(ghazghkull)
    ork_army.add_unit(bodyguard)
    enemy_army.add_unit(target)
    ghazghkull.attach_to_unit(bodyguard)
    _deploy(bodyguard, 0.0, 0.0)
    _deploy(ghazghkull, 0.0, 0.0)
    _deploy(target, 2.0, 0.0)
    _register_units(game, bodyguard, ghazghkull, target)

    no_waaagh_mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=target)
    assert int(no_waaagh_mods.get("hit", 0) or 0) == 1
    assert int(no_waaagh_mods.get("wound", 0) or 0) == 1
    assert no_waaagh_mods.get("crit_hit_threshold") is None

    _mark_waaagh_active(ork_army, ork_player)
    waaagh_mods = bodyguard.get_leading_attack_roll_modifiers("melee", target=target)
    assert int(waaagh_mods.get("hit", 0) or 0) == 1
    assert int(waaagh_mods.get("wound", 0) or 0) == 1
    assert int(waaagh_mods.get("crit_hit_threshold", 0) or 0) == 5


def test_ghazghkulls_waaagh_banner_grants_makari_aura_only_while_waaagh_active():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    ghazghkull = _actual_unit("Ghazghkull Thraka")
    ally = _actual_unit("Boyz")
    target = _actual_unit("Boyz")
    ork_army.add_unit(ghazghkull)
    ork_army.add_unit(ally)
    enemy_army.add_unit(target)
    _deploy(ghazghkull, 18.0, 0.0)
    _deploy(ally, 2.0, 0.0)
    _deploy(target, 4.0, 0.0)
    makari = next(model for model in ghazghkull.models if model.name == "Makari")
    makari.set_location(0.0, 0.0, 0.0, 0.0)
    _register_units(game, ghazghkull, ally, target)

    ally_weapon = next(wg for wg in ally.models[0].wargear if wg.is_melee())
    ally_profile = next(iter(ally_weapon.profiles.values()))

    inactive = get_aura_weapon_keyword_bonuses(
        ally,
        ally_profile,
        target_unit=target,
        attacker_model=ally.models[0],
        game_map=game.map,
    )
    assert inactive == []

    _mark_waaagh_active(ork_army, ork_player)
    active = get_aura_weapon_keyword_bonuses(
        ally,
        ally_profile,
        target_unit=target,
        attacker_model=ally.models[0],
        game_map=game.map,
    )
    assert any(
        str(entry.get("attack_type", "")).lower() == "melee"
        and str(entry.get("keyword", "")).upper() == "LETHAL HITS"
        for entry in list(active or [])
    )


def test_kill_rig_spirit_of_gork_queues_and_applies_temporary_melee_bonuses():
    game, ork_army, enemy_army, ork_player, _enemy_player = _build_game()
    kill_rig = _actual_unit("Kill Rig")
    ally = _actual_unit("Boyz")
    target = _actual_unit("Boyz")
    ork_army.add_unit(kill_rig)
    ork_army.add_unit(ally)
    enemy_army.add_unit(target)
    _deploy(kill_rig, 0.0, 0.0)
    _deploy(ally, 4.0, 0.0)
    _deploy(target, 20.0, 0.0)
    _register_units(game, kill_rig, ally, target)
    game.phase = BattleRoundPhases.FIGHT_PHASE

    game._on_phase_start_spirit_of_gork(player=ork_player, phase=game.phase)
    request = _find_choose_quarry_request(game, ability="spirit_of_gork")
    assert request is not None
    assert str(getattr(request, "decision_type", "") or "") == DECISION_CHOOSE_QUARRY
    assert any(str(getattr(option, "label", "") or "") == "None" for option in list(request.options or []))

    target_option = next(
        option
        for option in list(request.options or [])
        if str((option.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(ally) or "")
    )
    with patch("warhammer40k_ai.utility.dice.get_roll", side_effect=[6]):
        result = resolve_decision_command(game, request, target_option.option_id, player_id=ork_player.id)
    assert bool(getattr(result, "ok", False)) is True

    melee_weapon_name = next(wg.name for wg in ally.models[0].wargear if wg.is_melee())
    strength_bonus, _strength_reasons = ally.models[0].get_temporary_weapon_strength_bonus(melee_weapon_name)
    keyword_bonuses = list(ally.models[0].get_temporary_weapon_keyword_bonuses(melee_weapon_name) or [])
    assert int(strength_bonus) == 1
    assert any(str(entry.get("keyword", "")).upper() == "LETHAL HITS" for entry in keyword_bonuses)
