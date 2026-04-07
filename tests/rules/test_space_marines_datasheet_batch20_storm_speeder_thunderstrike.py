from __future__ import annotations

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
    sm_army = Army.with_detachment("Space Marines", detachment_type="Other")
    sm_army.faction_id = "SM"
    enemy_army = Army.with_detachment("Enemy", detachment_type="Other")
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


def _first_profile(unit: Unit, *, ranged: bool):
    for model in list(unit.models or []):
        for wargear in list(getattr(model, "wargear", []) or []):
            is_ranged = bool(getattr(wargear, "is_ranged", lambda: False)())
            is_melee = bool(getattr(wargear, "is_melee", lambda: False)())
            if ranged and not is_ranged:
                continue
            if not ranged and not is_melee:
                continue
            profiles = getattr(wargear, "profiles", {}) or {}
            if "default" in profiles:
                return profiles["default"]
    kind = "ranged" if ranged else "melee"
    raise AssertionError(f"No {kind} profile found for {unit.name!r}")


def test_thunderstrike_marks_hit_monster_vehicle_for_adeptus_astartes_ranged_wound_bonus() -> None:
    game, sm_army, enemy_army, sm_player = _build_game()
    thunderstrike = _actual_unit("Storm Speeder Thunderstrike")
    ally = _actual_unit("Intercessor Squad")
    vehicle_target = _actual_unit("Rhino")
    infantry_target = _actual_unit("Scout Squad")
    sm_army.add_unit(thunderstrike)
    sm_army.add_unit(ally)
    enemy_army.add_unit(vehicle_target)
    enemy_army.add_unit(infantry_target)

    _set_unit_position(thunderstrike, 0.0, 0.0)
    _set_unit_position(ally, 2.0, 0.0)
    _set_unit_position(vehicle_target, 12.0, 0.0)
    _set_unit_position(infantry_target, 14.0, 0.0)
    game.map.units = [thunderstrike, ally, vehicle_target, infantry_target]
    game.rebuild_entity_registry()

    specs = thunderstrike.unit_post_shoot_keyword_wound_bonus_specs()
    assert len(specs) == 1
    assert str(specs[0].get("source", "") or "") == "Thunderstrike"
    assert str(specs[0].get("keyword", "") or "") == "adeptus astartes"
    assert str(specs[0].get("attack_type", "") or "") == "ranged"
    assert int(specs[0].get("bonus", 0) or 0) == 1
    assert tuple(specs[0].get("target_keywords_any", ()) or ()) == ("monster", "vehicle")

    game._on_unit_shooting_resolved_post_shoot_keyword_wound_bonus(
        attacker_unit=thunderstrike,
        hits_by_target={vehicle_target: 1, infantry_target: 1},
    )

    pending = list(game.decision_queue.list() or [])
    assert len(pending) == 1
    request = pending[0]
    assert request.decision_type == DECISION_CHOOSE_QUARRY
    assert len(request.options) == 1
    assert str(request.options[0].label or "") == "Rhino"
    ctx = request.context or {}
    assert str(ctx.get("ability", "") or "") == "post_shoot_keyword_wound_bonus"
    assert str(ctx.get("ability_name", "") or "") == "Thunderstrike"
    assert str(ctx.get("keyword_phrase", "") or "") == "adeptus astartes"
    assert str(ctx.get("attack_type", "") or "") == "ranged"
    assert int(ctx.get("wound_bonus", 0) or 0) == 1

    resolve_decision_command(game, request, request.options[0].option_id, player_id=sm_player.id)

    target_sr = getattr(vehicle_target, "special_rules", {}) or {}
    assert bool(target_sr.get("post_shoot_keyword_wound_bonus_active", False)) is True
    assert str(target_sr.get("post_shoot_keyword_wound_bonus_expires_phase", "") or "") == "SHOOTING_PHASE"
    assert str(target_sr.get("post_shoot_keyword_wound_bonus_phrase", "") or "") == "adeptus astartes"
    assert str(target_sr.get("post_shoot_keyword_wound_bonus_attack_type", "") or "") == "ranged"
    assert int(target_sr.get("post_shoot_keyword_wound_bonus_value", 0) or 0) == 1
    assert "Thunderstrike" in str(target_sr.get("post_shoot_keyword_wound_bonus_source", "") or "")

    ranged_mods = ally.get_unit_wound_reroll_modifiers(
        "ranged",
        target=vehicle_target,
        attacker_model=ally.models[0],
        weapon_profile=_first_profile(ally, ranged=True),
    )
    melee_mods = ally.get_unit_wound_reroll_modifiers(
        "melee",
        target=vehicle_target,
        attacker_model=ally.models[0],
        weapon_profile=_first_profile(ally, ranged=False),
    )
    infantry_mods = ally.get_unit_wound_reroll_modifiers(
        "ranged",
        target=infantry_target,
        attacker_model=ally.models[0],
        weapon_profile=_first_profile(ally, ranged=True),
    )

    assert int(ranged_mods.get("wound", 0) or 0) == 1
    assert any("Thunderstrike" in reason for reason in list(ranged_mods.get("wound_reasons", ()) or ()))
    assert int(melee_mods.get("wound", 0) or 0) == 0
    assert int(infantry_mods.get("wound", 0) or 0) == 0
