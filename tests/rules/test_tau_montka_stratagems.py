from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.utility.entity_ids import get_entity_id
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear, WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        keywords=None,
        faction_keywords=None,
        wounds: str = "4",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": "T'au Empire"}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "4",
                "W": str(wounds),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "0",
                "inv_sv_descr": "",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(name: str, *, keywords=None, faction_keywords=None, wounds: str = "4") -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Mont'ka")
    tau_army.faction_id = "TAU"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    tau_player = Player("Tau", control=PlayerControl.LOCAL, army=tau_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(tau_player)
    game.add_player(enemy_player)

    tau_player.command_points = 10
    enemy_player.command_points = 10
    tau_army.configure_rule_managers(force=True)
    tau_player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    return game, tau_player, enemy_player, tau_army, enemy_army


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _destroy_unit(unit: Unit, game_map) -> object:
    model = unit.models[0]
    model.wounds = 0
    model.die(game_map=game_map)
    return model


class _RangedWargear:
    name = "Test Rifle"

    @staticmethod
    def is_melee() -> bool:
        return False

    @staticmethod
    def is_ranged() -> bool:
        return True


def _ranged_profile() -> WargearProfile:
    return WargearProfile(
        "Test Rifle",
        {
            "range": "24",
            "A": "1",
            "BS_WS": "3+",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
        },
        parent_wargear=_RangedWargear(),
    )


def test_pinpoint_counter_offensive_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008812002")
    assert desc is not None
    assert desc.name == "Pinpoint Counter-Offensive"
    assert desc.effect == "tau_non_kroot_hit_reroll_vs_destroying_enemy"
    assert bool(desc.effect_params.get("reroll_hit_full", False)) is True


def test_aggressive_mobility_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008812003")
    assert desc is not None
    assert desc.name == "Aggressive Mobility"
    assert desc.effect == "advance_no_roll_plus_6"
    assert int(desc.effect_params.get("advance_distance", 0) or 0) == 6


def test_aggressive_mobility_sets_fixed_advance_and_cleans_up_at_phase_end():
    game, tau_player, _enemy_player, tau_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    tau_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    _set_phase(game, tau_player, "MOVEMENT_PHASE", 0)
    ok = tau_player.stratagems.use("AGGRESSIVE MOBILITY", unit=unit, phase_name="Movement phase")
    assert ok
    assert int(tau_player.command_points or 0) == 9

    effect = unit._get_advance_no_roll_effect()
    assert effect is not None
    assert int(effect.get("distance", 0) or 0) == 6

    roll = unit.prepare_advance()
    assert int(roll or 0) == 6
    assert int(getattr(unit.round_state, "advance_roll", 0) or 0) == 6

    game.event_system.publish("phase_end", player=tau_player, phase=SimpleNamespace(name="MOVEMENT_PHASE"))
    assert unit._get_advance_no_roll_effect() is None


def test_aggressive_mobility_requires_target_not_selected_to_move():
    game, tau_player, _enemy_player, tau_army, _enemy_army = _build_game()
    unit = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    tau_army.add_unit(unit)
    _deploy_unit(game, unit, 10.0, 10.0)

    _set_phase(game, tau_player, "MOVEMENT_PHASE", 0)
    unit.round_state.moved_this_round = True
    ok = tau_player.stratagems.use("AGGRESSIVE MOBILITY", unit=unit, phase_name="Movement phase")
    assert not ok


def test_counterfire_defence_systems_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008812007")
    assert desc is not None
    assert desc.name == "Counterfire Defence Systems"
    assert desc.effect == "defensive_damage_reduction"
    assert int(desc.effect_params.get("damage_reduction", 0) or 0) == 1


def test_counterfire_defence_systems_queues_and_reduces_damage_until_phase_end():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    defender = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 16.0, 10.0)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])
    pending = [
        r for r in list(tau_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "COUNTERFIRE DEFENCE SYSTEMS"
    ]
    assert len(pending) == 1

    ok = tau_player.stratagems.use(
        "COUNTERFIRE DEFENCE SYSTEMS",
        unit=defender,
        attacking_unit=attacker,
        dequeue=True,
    )
    assert ok
    assert int(tau_player.command_points or 0) == 8
    entries = list(defender.special_rules.get("defensive_damage_reductions", []) or [])
    assert any(
        int(entry.get("value", 0) or 0) == 1
        and str(entry.get("expires_phase", "") or "").strip().upper() == "SHOOTING_PHASE"
        for entry in entries
        if isinstance(entry, dict)
    )

    profile = Wargear(
        {
            "name": "Enemy Rifle",
            "type": "Ranged",
            "range": "24",
            "A": "1",
            "BS_WS": "4+",
            "S": "4",
            "AP": "0",
            "D": "2",
            "description": "",
        }
    ).profiles["default"]
    target_model = defender.models[0]
    target_model.wounds = 4
    reduced = profile._damage_target_with_tracking(
        target_model,
        attacker.models[0],
        {},
        allow_rerolls=False,
    )
    assert int(reduced.get("damage_applied", 0) or 0) == 1

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert not list(defender.special_rules.get("defensive_damage_reductions", []) or [])

    target_model.wounds = 4
    normal = profile._damage_target_with_tracking(
        target_model,
        attacker.models[0],
        {},
        allow_rerolls=False,
    )
    assert int(normal.get("damage_applied", 0) or 0) == 2


def test_pinpoint_counter_offensive_queues_after_non_kroot_tau_unit_destroyed():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    destroyed = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Shooters",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(destroyed)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    dead_model = _destroy_unit(destroyed, game.map)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_destroyed",
        unit=destroyed,
        last_model=dead_model,
        destroyed_by_unit=enemy,
    )

    pending = [
        r
        for r in list(tau_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "PINPOINT COUNTER-OFFENSIVE"
    ]
    assert len(pending) == 1


def test_pinpoint_counter_offensive_marks_enemy_and_grants_hit_rerolls_for_non_kroot_tau_attackers():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    destroyed = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    attacker = _make_unit(
        "Crisis Team",
        keywords=["INFANTRY", "BATTLESUIT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Destroyer",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(destroyed)
    tau_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _deploy_unit(game, attacker, 12.0, 10.0)
    _deploy_unit(game, enemy, 18.0, 10.0)
    _deploy_unit(game, other_enemy, 24.0, 10.0)
    dead_model = _destroy_unit(destroyed, game.map)

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_destroyed",
        unit=destroyed,
        last_model=dead_model,
        destroyed_by_unit=enemy,
    )

    ok = tau_player.stratagems.use(
        "PINPOINT COUNTER-OFFENSIVE",
        unit=destroyed,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok
    assert int(tau_player.command_points or 0) == 9

    profile = _ranged_profile()
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        hit = profile._hit_target_with_tracking(enemy, attacker.models[0], {}, roll_value=1)
    assert int(hit.get("reroll", 0) or 0) == 5
    assert "Pinpoint Counter-Offensive" in list(hit.get("reroll_full_reasons", []) or [])

    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        off_target_hit = profile._hit_target_with_tracking(other_enemy, attacker.models[0], {}, roll_value=1)
    assert int(off_target_hit.get("reroll", 0) or 0) == 0


def test_pinpoint_counter_offensive_excludes_kroot_units_from_trigger_and_effect():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    destroyed_kroot = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    attacker_kroot = _make_unit(
        "Kroot Rifle Team",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    destroyed_tau = _make_unit(
        "Strike Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Destroyer",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(destroyed_kroot)
    tau_army.add_unit(attacker_kroot)
    tau_army.add_unit(destroyed_tau)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyed_kroot, 10.0, 10.0)
    _deploy_unit(game, attacker_kroot, 12.0, 10.0)
    _deploy_unit(game, destroyed_tau, 10.0, 14.0)
    _deploy_unit(game, enemy, 18.0, 10.0)

    dead_kroot_model = _destroy_unit(destroyed_kroot, game.map)
    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish(
        "unit_destroyed",
        unit=destroyed_kroot,
        last_model=dead_kroot_model,
        destroyed_by_unit=enemy,
    )
    pending_after_kroot = [
        r
        for r in list(tau_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "PINPOINT COUNTER-OFFENSIVE"
    ]
    assert not pending_after_kroot

    dead_tau_model = _destroy_unit(destroyed_tau, game.map)
    game.event_system.publish(
        "unit_destroyed",
        unit=destroyed_tau,
        last_model=dead_tau_model,
        destroyed_by_unit=enemy,
    )
    ok = tau_player.stratagems.use(
        "PINPOINT COUNTER-OFFENSIVE",
        unit=destroyed_tau,
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert ok

    profile = _ranged_profile()
    with patch("warhammer40k_ai.units.wargear.get_roll", return_value=5):
        hit = profile._hit_target_with_tracking(enemy, attacker_kroot.models[0], {}, roll_value=1)
    assert int(hit.get("reroll", 0) or 0) == 0
    assert "Pinpoint Counter-Offensive" not in list(hit.get("reroll_full_reasons", []) or [])


def test_combat_debarkation_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008812005")
    assert desc is not None
    assert desc.name == "Combat Debarkation"
    assert desc.effect == "closest_eligible_enemy_wound_reroll"
    assert bool(desc.effect_params.get("closest_target_only", False)) is True


def test_focused_fire_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008812004")
    assert desc is not None
    assert desc.name == "Focused Fire"
    assert desc.effect == "target_lock_and_ranged_ap_bonus"
    assert int(desc.effect_params.get("ap_bonus", 0) or 0) == 1


def test_pulse_onslaught_descriptor_registered():
    desc = get_stratagem_tool_descriptor(stratagem_id="000008812006")
    assert desc is not None
    assert desc.name == "Pulse Onslaught"
    assert desc.effect == "apply_shaken_mobility_debuff"
    assert int(desc.effect_params.get("move_penalty", 0) or 0) == -2


def test_combat_debarkation_enables_closest_target_wound_rerolls():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    transport = _make_unit(
        "Devilfish",
        keywords=["VEHICLE", "TRANSPORT"],
        faction_keywords=["T'AU EMPIRE"],
    )
    shooter = _make_unit(
        "Breacher Team",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(transport)
    tau_army.add_unit(shooter)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, transport, 8.0, 10.0)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)

    shooter.round_state.disembarked_this_round = True
    shooter.round_state.disembarked_from_transport_id = get_entity_id(transport)

    _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    ok = tau_player.stratagems.use("COMBAT DEBARKATION", unit=shooter, phase_name="Shooting phase")
    assert ok
    assert int(tau_player.command_points or 0) == 9

    profile = _ranged_profile()
    with patch.object(Unit, "is_target_closest_eligible", return_value=True):
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 1, 5, 6]):
            result_closest = profile.attack(enemy, shooter.models[0], game.map)
    assert result_closest is not None
    wound_entries = list(result_closest.wound_results or [])
    assert wound_entries
    assert int(wound_entries[0].get("reroll", 0) or 0) == 5
    assert "COMBAT DEBARKATION" in " ".join(list(wound_entries[0].get("reroll_full_reasons", []) or []))

    with patch.object(Unit, "is_target_closest_eligible", return_value=False):
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[4, 1, 6]):
            result_not_closest = profile.attack(enemy, shooter.models[0], game.map)
    assert result_not_closest is not None
    wound_entries = list(result_not_closest.wound_results or [])
    assert wound_entries
    assert int(wound_entries[0].get("reroll", 0) or 0) == 0


def test_focused_fire_applies_target_lock_and_ap_bonus():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    first = _make_unit(
        "Strike Team A",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    second = _make_unit(
        "Strike Team B",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    marked_enemy = _make_unit(
        "Marked Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(first)
    tau_army.add_unit(second)
    enemy_army.add_unit(marked_enemy)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, first, 10.0, 10.0)
    _deploy_unit(game, second, 12.0, 10.0)
    _deploy_unit(game, marked_enemy, 16.0, 10.0)
    _deploy_unit(game, other_enemy, 18.0, 12.0)

    _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    ok = tau_player.stratagems.use(
        "FOCUSED FIRE",
        units=[first, second],
        enemy_unit=marked_enemy,
        phase_name="Shooting phase",
    )
    assert ok
    assert int(tau_player.command_points or 0) == 9

    marked_id = get_entity_id(marked_enemy)
    for unit in (first, second):
        sr = dict(getattr(unit, "special_rules", {}) or {})
        assert bool(sr.get("tau_focused_fire_active")) is True
        assert str(sr.get("tau_focused_fire_target_id", "") or "") == marked_id
        assert int(sr.get("tau_focused_fire_ap_bonus", 0) or 0) == 1

    profile = _ranged_profile()
    shooter_model = first.models[0]
    can_target_marked = first._can_model_shoot_weapon_at_target(shooter_model, profile, marked_enemy, game.map)
    can_target_other = first._can_model_shoot_weapon_at_target(shooter_model, profile, other_enemy, game.map)
    assert can_target_marked
    assert not can_target_other
    assert int(profile.get_effective_ap(shooter_model, marked_enemy)) == -1


def test_focused_fire_cannot_be_used_in_battle_round_four_or_five():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    first = _make_unit(
        "Strike Team A",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    second = _make_unit(
        "Strike Team B",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(first)
    tau_army.add_unit(second)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, first, 10.0, 10.0)
    _deploy_unit(game, second, 12.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)

    game.turn = 4
    _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    ok = tau_player.stratagems.use(
        "FOCUSED FIRE",
        units=[first, second],
        enemy_unit=enemy,
        phase_name="Shooting phase",
    )
    assert not ok


def test_pulse_onslaught_queues_after_shooting_and_applies_shaken_until_opponent_turn_end():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Fire Warriors",
        keywords=["INFANTRY"],
        faction_keywords=["T'AU EMPIRE"],
    )
    enemy_target = _make_unit(
        "Enemy Infantry",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    enemy_monster = _make_unit(
        "Enemy Monster",
        keywords=["MONSTER"],
        faction_keywords=["ENEMY"],
        wounds="8",
    )
    tau_army.add_unit(shooter)
    enemy_army.add_unit(enemy_target)
    enemy_army.add_unit(enemy_monster)
    _deploy_unit(game, shooter, 10.0, 10.0)
    _deploy_unit(game, enemy_target, 16.0, 10.0)
    _deploy_unit(game, enemy_monster, 18.0, 10.0)

    _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    shooter.round_state.shot_this_round = True
    game.event_system.publish(
        "unit_shooting_resolved",
        attacker_unit=shooter,
        hits_by_target={enemy_target: 2, enemy_monster: 1},
    )
    pending = [
        r
        for r in list(tau_player.stratagems.get_pending_reactions() or [])
        if str(r.get("stratagem", "") or "").strip().upper() == "PULSE ONSLAUGHT"
    ]
    assert len(pending) == 1
    enemy_candidates = list(pending[0].get("enemy_candidates") or pending[0].get("candidates") or [])
    assert enemy_target in enemy_candidates
    assert enemy_monster not in enemy_candidates

    ok = tau_player.stratagems.use(
        "PULSE ONSLAUGHT",
        unit=shooter,
        enemy_unit=enemy_target,
        dequeue=True,
        phase_name="Shooting phase",
    )
    assert ok
    assert int(tau_player.command_points or 0) == 8
    sr = dict(getattr(enemy_target, "special_rules", {}) or {})
    assert bool(sr.get("aflame_active")) is True
    assert int(sr.get("aflame_move_penalty", 0) or 0) == -2
    assert int(sr.get("aflame_advance_penalty", 0) or 0) == -2
    assert int(sr.get("aflame_charge_penalty", 0) or 0) == -2

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    sr_after = dict(getattr(enemy_target, "special_rules", {}) or {})
    assert bool(sr_after.get("aflame_active", False)) is False
