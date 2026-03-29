from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command
from warhammer40k_ai.utility.entity_ids import get_entity_id


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "T'au Empire",
        keywords=None,
        faction_keywords=None,
        movement: int = 8,
        wounds: int = 3,
        model_count: int = 1,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            if faction_name == "T'au Empire":
                faction_keywords = ["T'AU EMPIRE"]
            else:
                faction_keywords = [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        count = max(1, int(model_count or 1))
        self.datasheets_unit_composition = [{"description": f"{count} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{count} models", "cost": 100}]
        self.datasheets_models = [
            {
                "M": str(int(movement)),
                "T": "4",
                "Sv": "4",
                "W": str(int(wounds)),
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
        self.attached_to_names = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "T'au Empire",
    keywords=None,
    faction_keywords=None,
    movement: int = 8,
    wounds: int = 3,
    quantity: int = 1,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            movement=movement,
            wounds=wounds,
            model_count=quantity,
        ),
        quantity=max(1, int(quantity or 1)),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    tau_army = Army("T'au Empire", "Kroot Hunting Pack")
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
        raise AssertionError(f"Failed to place {getattr(unit, 'name', 'Unit')}")


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = SimpleNamespace(name=phase_name)
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _find_request(game: Game, decision_type: str, *, ability: str | None = None):
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        context = dict(getattr(request, "context", {}) or {})
        if ability is not None and str(context.get("ability", "") or "") != str(ability):
            continue
        return request
    return None


class _RangedWargear:
    name = "Test Rifle"

    @staticmethod
    def is_melee() -> bool:
        return False

    @staticmethod
    def is_ranged() -> bool:
        return True


class _MeleeWargear:
    name = "Test Blade"

    @staticmethod
    def is_melee() -> bool:
        return True

    @staticmethod
    def is_ranged() -> bool:
        return False


def _ranged_profile(*, skill: str = "4+", ap: str = "0") -> WargearProfile:
    return WargearProfile(
        "Ranged",
        {
            "range": "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": "4",
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=_RangedWargear(),
    )


def _melee_profile(*, skill: str = "3+", ap: str = "0") -> WargearProfile:
    return WargearProfile(
        "Melee",
        {
            "range": "Melee",
            "A": "2",
            "BS_WS": str(skill),
            "S": "4",
            "AP": str(ap),
            "D": "1",
            "description": "",
        },
        parent_wargear=_MeleeWargear(),
    )


def _mark_destroyed(unit: Unit, game_map) -> None:
    for model in list(getattr(unit, "models", []) or []):
        model.wounds = 0
    if unit in list(getattr(game_map, "units", []) or []):
        game_map.units.remove(unit)
    unit.is_alive = lambda: False


def test_kroot_hunting_pack_descriptors_registered():
    expected = {
        "000008822002": ("Join the Hunt", "clone_unit_to_strategic_reserves"),
        "000008822003": ("A Trap Well Laid", "conditional_kroot_ap_bonus_vs_selected_hit_enemy_unless_battleshocked"),
        "000008822004": ("Emp Grenades", "enemy_vehicle_ws_bs_penalty"),
        "000008822005": ("The Grisly Feast", "battle_shock_enemies_within_range_in_next_opponent_command_phase"),
        "000008822006": ("Guerrilla Warriors", "shoot_and_charge_after_fall_back"),
        "000008822007": ("Hidden Hunters", "ranged_targeting_range_restriction"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        desc = get_stratagem_tool_descriptor(stratagem_id=stratagem_id)
        assert desc is not None
        assert desc.name == expected_name
        assert desc.effect == expected_effect


def test_guerrilla_warriors_queues_after_fall_back_and_enables_shoot_and_charge():
    game, tau_player, _enemy_player, tau_army, _enemy_army = _build_game()
    kroot = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    tau_army.add_unit(kroot)
    _deploy_unit(game, kroot, 10.0, 10.0)
    game.rebuild_entity_registry()

    profile = _ranged_profile()
    assert not kroot.can_shoot_after_fall_back(profile)
    assert not kroot.can_charge_after_fall_back()

    _set_phase(game, tau_player, "MOVEMENT_PHASE", 0)
    kroot.round_state.fell_back_this_round = True
    game.event_system.publish("unit_move_ended", unit=kroot, action="fall_back")

    pending = _pending_by_name(tau_player.stratagems, "GUERRILLA WARRIORS")
    assert pending is not None
    ok = tau_player.stratagems.use("GUERRILLA WARRIORS", unit=kroot, phase_name="Movement phase", dequeue=True)
    assert ok
    assert int(tau_player.command_points or 0) == 9
    assert kroot.can_shoot_after_fall_back(profile)
    assert kroot.can_charge_after_fall_back()


def test_hidden_hunters_queues_on_enemy_target_selection_and_applies_range_lock():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    defender = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(defender)
    enemy_army.add_unit(attacker)
    _deploy_unit(game, defender, 10.0, 10.0)
    _deploy_unit(game, attacker, 22.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[defender])

    pending = _pending_by_name(tau_player.stratagems, "HIDDEN HUNTERS")
    assert pending is not None
    ok = tau_player.stratagems.use("HIDDEN HUNTERS", unit=defender, phase_name="Shooting phase", dequeue=True)
    assert ok
    assert int(tau_player.command_points or 0) == 9

    sr = dict(getattr(defender, "special_rules", {}) or {})
    assert bool(sr.get("tau_neuroweb_system_jammer_active")) is True
    assert int(sr.get("tau_neuroweb_system_jammer_targeting_range", 0) or 0) == 18
    assert str(sr.get("tau_neuroweb_system_jammer_source", "") or "") == "HIDDEN HUNTERS"

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert "tau_neuroweb_system_jammer_active" not in defender.special_rules


def test_join_the_hunt_replaces_destroyed_kroot_unit_in_strategic_reserves():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    destroyed = _make_unit(
        "Kroot Hounds",
        keywords=["BEASTS", "KROOT", "HOUNDS"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
        quantity=5,
    )
    enemy = _make_unit(
        "Enemy Attackers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(destroyed)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, destroyed, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    existing_ids = {id(entry) for entry in list(tau_army.units or [])}
    _set_phase(game, tau_player, "FIGHT_PHASE", 0)
    _mark_destroyed(destroyed, game.map)

    game.event_system.publish("unit_destroyed", unit=destroyed, destroyed_by_unit=enemy)
    assert _pending_by_name(tau_player.stratagems, "JOIN THE HUNT") is not None
    assert tau_player.stratagems.use("JOIN THE HUNT", destroyed_unit=destroyed, phase_name="Fight phase", dequeue=True)

    replacements = [entry for entry in list(tau_army.units or []) if id(entry) not in existing_ids]
    assert len(replacements) == 1
    replacement = replacements[0]
    assert replacement is not destroyed
    assert str(getattr(replacement, "reserve_status", "") or "") == "strategic_reserves"
    assert bool(replacement.is_in_reserves())
    assert bool(replacement.is_alive())
    assert int(getattr(replacement, "starting_model_count", 0) or 0) == int(getattr(destroyed, "starting_model_count", 0) or 0)


def test_emp_grenades_queues_in_shooting_phase_and_worsens_ballistic_skill():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    grenadier = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT", "GRENADES"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    enemy_vehicle = _make_unit(
        "Enemy Tank",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    secondary_target = _make_unit(
        "Auxiliary Kroot",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    tau_army.add_unit(grenadier)
    tau_army.add_unit(secondary_target)
    enemy_army.add_unit(enemy_vehicle)
    _deploy_unit(game, grenadier, 10.0, 10.0)
    _deploy_unit(game, secondary_target, 13.0, 10.0)
    _deploy_unit(game, enemy_vehicle, 17.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=enemy_vehicle, target_units=[grenadier])

    pending = _pending_by_name(tau_player.stratagems, "EMP GRENADES")
    assert pending is not None
    ok = tau_player.stratagems.use(
        "EMP GRENADES",
        unit=grenadier,
        enemy_unit=enemy_vehicle,
        phase_name="Shooting phase",
        dequeue=True,
    )
    assert ok
    assert int(tau_player.command_points or 0) == 9

    profile = _ranged_profile(skill="4+")
    hit = profile._hit_target_with_tracking(
        secondary_target,
        enemy_vehicle.models[0],
        {"target_model": secondary_target.models[0]},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit.get("base_skill", 0) or 0) == 5
    assert any("EMP GRENADES" in str(effect) for effect in list(hit.get("special_effects", []) or []))

    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))
    assert "tau_emp_grenades_active" not in enemy_vehicle.special_rules


def test_emp_grenades_queues_in_fight_phase_and_worsens_weapon_skill():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    grenadier = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT", "GRENADES"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    friendly_target = _make_unit(
        "Kroot Hounds",
        keywords=["BEASTS", "KROOT", "HOUNDS"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    enemy_vehicle = _make_unit(
        "Enemy Walker",
        faction_name="Enemy",
        keywords=["VEHICLE"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(grenadier)
    tau_army.add_unit(friendly_target)
    enemy_army.add_unit(enemy_vehicle)
    _deploy_unit(game, grenadier, 10.0, 10.0)
    _deploy_unit(game, friendly_target, 12.0, 10.0)
    _deploy_unit(game, enemy_vehicle, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("fight_unit_selected", unit=enemy_vehicle, selecting_player=enemy_player)

    pending = _pending_by_name(tau_player.stratagems, "EMP GRENADES")
    assert pending is not None
    ok = tau_player.stratagems.use(
        "EMP GRENADES",
        unit=grenadier,
        enemy_unit=enemy_vehicle,
        phase_name="Fight phase",
        dequeue=True,
    )
    assert ok

    profile = _melee_profile(skill="3+")
    hit = profile._hit_target_with_tracking(
        friendly_target,
        enemy_vehicle.models[0],
        {"target_model": friendly_target.models[0]},
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert int(hit.get("base_skill", 0) or 0) == 4
    assert any("EMP GRENADES" in str(effect) for effect in list(hit.get("special_effects", []) or []))


def test_the_grisly_feast_triggers_battleshock_tests_in_next_opponent_command_phase():
    game, tau_player, enemy_player, tau_army, enemy_army = _build_game()
    kroot = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    destroyed_enemy = _make_unit(
        "Destroyed Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    nearby_enemy = _make_unit(
        "Nearby Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    far_enemy = _make_unit(
        "Far Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(kroot)
    enemy_army.add_unit(destroyed_enemy)
    enemy_army.add_unit(nearby_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy_unit(game, kroot, 10.0, 10.0)
    _deploy_unit(game, destroyed_enemy, 11.5, 10.0)
    _deploy_unit(game, nearby_enemy, 15.0, 10.0)
    _deploy_unit(game, far_enemy, 24.0, 10.0)
    game.rebuild_entity_registry()

    test_calls: list[tuple[str, int, int, str, bool]] = []
    nearby_enemy.is_below_half_strength = lambda: True
    far_enemy.is_below_half_strength = lambda: False

    def _record_test(unit_name: str, unit: Unit):
        def _inner(current_turn=0):
            rules = dict(getattr(unit, "special_rules", {}) or {})
            test_calls.append(
                (
                    unit_name,
                    int(current_turn or 0),
                    int(rules.get("battle_shock_test_modifier", 0) or 0),
                    str(rules.get("battle_shock_suppress_other_tests_source", "") or ""),
                    bool(rules.get("battle_shock_allow_suppressed_test")),
                )
            )
        return _inner

    nearby_enemy.take_battle_shock_test = _record_test("near", nearby_enemy)
    far_enemy.take_battle_shock_test = _record_test("far", far_enemy)

    _set_phase(game, tau_player, "FIGHT_PHASE", 0)
    game.event_system.publish("unit_destroyed", unit=destroyed_enemy, destroyed_by_unit=kroot)

    pending = _pending_by_name(tau_player.stratagems, "THE GRISLY FEAST")
    assert pending is not None
    ok = tau_player.stratagems.use("THE GRISLY FEAST", unit=kroot, phase_name="Fight phase", dequeue=True)
    assert ok

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)

    assert ("near", 1, -1, "THE GRISLY FEAST", True) in test_calls
    assert not any(entry[0] == "far" for entry in test_calls)


def test_a_trap_well_laid_queues_choose_quarry_and_applies_ranged_bonus_only_for_non_battleshocked_kroot():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Kroot Carnivores",
        keywords=["INFANTRY", "KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    other_enemy = _make_unit(
        "Other Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    enemy_army.add_unit(other_enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    _deploy_unit(game, other_enemy, 22.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tau_player, "SHOOTING_PHASE", 0)
    ok = tau_player.stratagems.use("A TRAP WELL LAID", unit=attacker, phase_name="Shooting phase")
    assert ok
    assert int(tau_player.command_points or 0) == 9

    game.event_system.publish("unit_shooting_resolved", attacker_unit=attacker, hits_by_target={enemy: 1})
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="post_shoot_ap_bonus")
    assert request is not None
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=tau_player.id)
    assert bool(getattr(result, "ok", False)) is True

    profile = _ranged_profile(skill="4+", ap="0")
    assert int(profile.get_effective_ap(attacker.models[0], enemy) or 0) == -1
    assert int(profile.get_effective_ap(attacker.models[0], other_enemy) or 0) == 0

    attacker.is_battle_shocked = lambda: True
    assert int(profile.get_effective_ap(attacker.models[0], enemy) or 0) == 0


def test_a_trap_well_laid_applies_melee_bonus_in_fight_phase():
    game, tau_player, _enemy_player, tau_army, enemy_army = _build_game()
    attacker = _make_unit(
        "Kroot Rampagers",
        keywords=["KROOT"],
        faction_keywords=["T'AU EMPIRE", "KROOT"],
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    tau_army.add_unit(attacker)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, attacker, 10.0, 10.0)
    _deploy_unit(game, enemy, 11.5, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, tau_player, "FIGHT_PHASE", 0)
    ok = tau_player.stratagems.use("A TRAP WELL LAID", unit=attacker, phase_name="Fight phase")
    assert ok

    game.event_system.publish("fight_attacks_resolved", unit=attacker, target_unit=enemy, hits_by_target={enemy: 1})
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="post_shoot_ap_bonus")
    assert request is not None
    option = next(
        opt
        for opt in list(request.options or [])
        if str((opt.payload or {}).get("target_unit_id", "") or "") == str(get_entity_id(enemy) or "")
    )
    result = resolve_decision_command(game, request, option.option_id, player_id=tau_player.id)
    assert bool(getattr(result, "ok", False)) is True

    profile = _melee_profile(skill="3+", ap="0")
    assert int(profile.get_effective_ap(attacker.models[0], enemy) or 0) == -1
