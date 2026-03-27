from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_QUARRY
from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
from warhammer40k_ai.engine.phase import BattleRoundPhases
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.decision_utils import resolve_decision_command


class _HashableNamespace(SimpleNamespace):
    __hash__ = object.__hash__


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Thousand Sons",
        keywords=None,
        faction_keywords=None,
        abilities=None,
        toughness: str = "4",
        wounds: str = "3",
        save: str = "3",
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = list(faction_keywords or [])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": str(toughness),
                "Sv": str(save),
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
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.transport = ""
        self.attached_to = []


def _make_unit(
    name: str,
    *,
    faction_name: str = "Thousand Sons",
    keywords=None,
    faction_keywords=None,
    abilities=None,
    toughness: str = "4",
    wounds: str = "3",
    save: str = "3",
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            abilities=abilities,
            toughness=toughness,
            wounds=wounds,
            save=save,
        )
    )


def _deep_strike_ability() -> dict:
    return {
        "name": "Deep Strike",
        "description": "Deep Strike",
        "type": "Core",
        "parameter": "",
    }


def _make_profile(
    *,
    name: str = "Warpflame",
    range_val: str = "18",
    strength: str = "4",
    damage: str = "1",
) -> WargearProfile:
    parent = SimpleNamespace(
        name=name,
        is_melee=lambda: False,
        is_ranged=lambda: True,
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": str(range_val),
            "A": "1",
            "BS_WS": "3+",
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


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
        crit_wound_threshold=None,
        crit_wound_reasons=(),
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    ts_army = Army("Thousand Sons", "Hexwarp Thrallband")
    ts_army.faction_id = "TS"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    ts_player = Player("TS", control=PlayerControl.LOCAL, army=ts_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(ts_player)
    game.add_player(enemy_player)

    ts_player.command_points = 10
    enemy_player.command_points = 10

    ts_army.configure_rule_managers(force=True)
    enemy_army.configure_rule_managers(force=True)
    _set_simple_deployment_zones(game, ts_player, enemy_player)
    _refresh(game, ts_player, enemy_player)
    return game, ts_player, enemy_player, ts_army, enemy_army


def _refresh(game: Game, *players: Player) -> None:
    for player in players:
        player.stratagems.refresh_available()
    game.rebuild_entity_registry()
    game.refresh_rule_subscribers()


def _set_simple_deployment_zones(game: Game, ts_player: Player, enemy_player: Player) -> None:
    def _in_deployment_zone(x: float, _y: float, player_id: str) -> bool:
        x_val = float(x)
        if str(player_id) == str(ts_player.id):
            return x_val <= 10.0
        if str(player_id) == str(enemy_player.id):
            return x_val >= 20.0
        return False

    game.is_position_in_deployment_zone = _in_deployment_zone
    game.is_position_wholly_in_deployment_zone = lambda x, y, _base, player_id: _in_deployment_zone(x, y, player_id)


def _deploy_unit(game: Game, unit: Unit, x: float, y: float) -> None:
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.embarked_in = None
    for model in list(getattr(unit, "models", []) or []):
        model.set_location(float(x), float(y), 0.0, 0.0)
    placed = game.map.place_unit(unit)
    if not placed:
        raise AssertionError(f"Failed to place unit {getattr(unit, 'name', 'Unit')}")


def _set_reserves_unit(unit: Unit, reserve_status: str = "strategic_reserves") -> None:
    unit.deployed = False
    unit.reserve_status = str(reserve_status)
    unit.embarked_in = None


def _set_phase(game: Game, player: Player, phase_name: str, current_player_index: int) -> None:
    game.phase = getattr(BattleRoundPhases, str(phase_name or "").strip().upper())
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=game.phase)


def _add_objective(game: Game, controller, *, x: float, y: float, name: str = "Objective"):
    location = _HashableNamespace(
        x=float(x),
        y=float(y),
        z=0.0,
        control_radius=3.0,
        removed=False,
        controlling_player=controller,
        sticky_controller=None,
        sticky_source="",
    )

    def _set_sticky_control(player, source: str = "") -> None:
        location.sticky_controller = player
        location.sticky_source = str(source or "")
        location.controlling_player = player

    location.set_sticky_control = _set_sticky_control
    location.update_control = lambda _game: None
    objective = SimpleNamespace(
        id=f"obj_{name.lower().replace(' ', '_')}",
        name=name,
        location=location,
    )
    objectives = list(getattr(game.map, "objectives", []) or [])
    objectives.append(objective)
    game.map.objectives = objectives
    return objective


def _pending_by_name(stratagems, name: str):
    name_u = str(name or "").strip().upper()
    return [
        reaction
        for reaction in list(stratagems.get_pending_reactions() or [])
        if str(reaction.get("stratagem", "") or "").strip().upper() == name_u
    ]


def _find_request(game: Game, decision_type: str, *, ability: str = ""):
    ability_key = str(ability or "").strip().lower()
    for request in list(game.decision_queue.list() or []):
        if str(getattr(request, "decision_type", "") or "") != str(decision_type):
            continue
        if ability_key and str((getattr(request, "context", {}) or {}).get("ability", "") or "").strip().lower() != ability_key:
            continue
        return request
    return None


def test_hexwarp_thrallband_stratagem_descriptors_registered():
    expected = {
        "000009742002": ("Warding Hex", "sticky_objective"),
        "000009742003": ("Wrath of the Doomed", "fight_on_death_after_attacks"),
        "000009742004": ("Strands of Time", "shoot_or_charge_after_fall_back"),
        "000009742005": ("Through the Veil", "temporary_deep_strike_with_hexwarp_flow_setup"),
        "000009742006": ("Scouring Warpflame", "ranged_ignores_cover_and_post_shoot_no_cover"),
        "000009742007": ("Kaleidoscopic Tempest", "stealth_and_conditional_cover"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_warding_hex_queues_and_makes_flow_objective_sticky():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(psyker)
    _refresh(game, ts_player)
    _deploy_unit(game, psyker, 15.0, 10.0)
    objective = _add_objective(game, ts_player, x=15.0, y=10.0, name="Center")

    _set_phase(game, ts_player, "COMMAND_PHASE", 0)
    pending = _pending_by_name(ts_player.stratagems, "WARDING HEX")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "WARDING HEX",
        unit=psyker,
        objective=objective,
        phase_name="Command phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert objective.location.sticky_controller is ts_player
    assert objective.location.sticky_source == "warding_hex"
    assert objective.location.controlling_player is ts_player


def test_warding_hex_rejects_objective_not_wholly_within_flow():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(psyker)
    _refresh(game, ts_player)
    _deploy_unit(game, psyker, 16.5, 10.0)
    _add_objective(game, ts_player, x=15.0, y=10.0, name="Flow Center")
    boundary = _add_objective(game, ts_player, x=19.0, y=10.0, name="Boundary")

    _set_phase(game, ts_player, "COMMAND_PHASE", 0)
    blocked = ts_player.stratagems.use(
        "WARDING HEX",
        unit=psyker,
        objective=boundary,
        phase_name="Command phase",
    )

    assert blocked is False
    assert int(ts_player.command_points or 0) == 10
    assert boundary.location.sticky_controller is None


def test_strands_of_time_queues_after_fall_back_and_requires_choice_outside_flow():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(psyker)
    _refresh(game, ts_player)
    _deploy_unit(game, psyker, 25.0, 10.0)
    psyker.round_state.fell_back_this_round = True

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=psyker, action="fall_back")
    pending = _pending_by_name(ts_player.stratagems, "STRANDS OF TIME")
    assert len(pending) == 1
    assert bool(pending[0].get("flow_of_magic")) is False
    assert list(pending[0].get("choice_options") or [])

    ok = ts_player.stratagems.use(
        "STRANDS OF TIME",
        unit=psyker,
        choice="SHOOT",
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert psyker.has_fell_back_and_shoot() is True
    assert psyker.can_charge_after_fall_back() is False

    game.event_system.publish("phase_end", player=ts_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert "thousand_sons_strands_of_time_shoot_active" not in dict(getattr(psyker, "special_rules", {}) or {})


def test_strands_of_time_in_flow_grants_shoot_and_charge():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    psyker = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(psyker)
    _refresh(game, ts_player)
    _deploy_unit(game, psyker, 15.0, 10.0)
    _add_objective(game, ts_player, x=15.0, y=10.0, name="Center")
    psyker.round_state.fell_back_this_round = True

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    game.event_system.publish("unit_move_ended", unit=psyker, action="fall_back")
    pending = _pending_by_name(ts_player.stratagems, "STRANDS OF TIME")
    assert len(pending) == 1
    assert bool(pending[0].get("flow_of_magic")) is True

    ok = ts_player.stratagems.use(
        "STRANDS OF TIME",
        unit=psyker,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok is True
    assert psyker.has_fell_back_and_shoot() is True
    assert psyker.can_charge_after_fall_back() is True


def test_through_the_veil_queues_during_reinforcements_step_and_cleans_rubric_deep_strike_on_arrival():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    rubrics = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY", "RUBRICAE", "RUBRIC MARINES"],
        faction_keywords=["THOUSAND SONS"],
    )
    ts_army.add_unit(rubrics)
    _set_reserves_unit(rubrics, "strategic_reserves")
    _refresh(game, ts_player)

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    game.handle_reserves_arrival_phase()
    pending = _pending_by_name(ts_player.stratagems, "THROUGH THE VEIL")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "THROUGH THE VEIL",
        unit=rubrics,
        phase_name="Movement phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert rubrics.has_deep_strike() is True

    for model in list(rubrics.models or []):
        model.set_location(12.0, 10.0, 0.0, 0.0)
    rubrics._finalize_reserves_arrival(turn=1, game_map=game.map)

    assert rubrics.has_deep_strike() is False
    assert "thousand_sons_through_the_veil_active" not in dict(getattr(rubrics, "special_rules", {}) or {})


def test_through_the_veil_scarabs_require_flow_and_use_six_inch_distance():
    game, ts_player, _enemy_player, ts_army, _enemy_army = _build_game()
    scarabs = _make_unit(
        "Scarab Occult Terminators",
        keywords=["THOUSAND SONS", "INFANTRY", "TERMINATOR", "SCARAB OCCULT TERMINATORS"],
        faction_keywords=["THOUSAND SONS"],
        abilities=[_deep_strike_ability()],
    )
    ts_army.add_unit(scarabs)
    _set_reserves_unit(scarabs, "strategic_reserves")
    _refresh(game, ts_player)
    _add_objective(game, ts_player, x=15.0, y=10.0, name="Center")

    _set_phase(game, ts_player, "MOVEMENT_PHASE", 0)
    ok = ts_player.stratagems.use("THROUGH THE VEIL", unit=scarabs, phase_name="Movement phase")

    assert ok is True
    assert float(scarabs.get_deep_strike_min_distance_override() or 0.0) == 6.0
    assert scarabs.is_through_the_veil_arrival_valid([(15.0, 10.0, 0.0, 0.0)], game=game, game_map=game.map) is True
    assert scarabs.is_through_the_veil_arrival_valid([(25.0, 10.0, 0.0, 0.0)], game=game, game_map=game.map) is False


def test_scouring_warpflame_grants_ignores_cover_and_post_shoot_no_cover():
    game, ts_player, _enemy_player, ts_army, enemy_army = _build_game()
    shooter = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY", "RUBRICAE", "RUBRIC MARINES"],
        faction_keywords=["THOUSAND SONS"],
    )
    target = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(shooter)
    enemy_army.add_unit(target)
    _refresh(game, ts_player, _enemy_player)
    _deploy_unit(game, shooter, 15.0, 10.0)
    _deploy_unit(game, target, 24.0, 10.0)
    _add_objective(game, ts_player, x=15.0, y=10.0, name="Center")

    _set_phase(game, ts_player, "SHOOTING_PHASE", 0)
    ok = ts_player.stratagems.use("SCOURING WARPFLAME", unit=shooter, phase_name="Shooting phase")

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    specs = shooter.unit_post_shoot_no_cover_specs()
    assert len(specs) == 1
    assert str(specs[0].get("source", "") or "") == "SCOURING WARPFLAME"

    game._on_unit_shooting_resolved_post_shoot_no_cover(
        attacker_unit=shooter,
        hits_by_target={target: 1},
        hit_models_by_target_weapon={},
    )
    request = _find_request(game, DECISION_CHOOSE_QUARRY, ability="post_shoot_no_cover")
    assert request is not None

    resolve_decision_command(game, request, request.options[0].option_id, player_id=ts_player.id)

    target_sr = getattr(target, "special_rules", {}) or {}
    assert bool(target_sr.get("post_shoot_no_cover_active", False)) is True

    profile = _make_profile()
    attack_instance = {"_aura_attack_mods": _aura_stub()}
    profile._hit_target_with_tracking(
        target,
        shooter.models[0],
        attack_instance,
        roll_value=3,
        allow_rerolls=False,
        log_roll=False,
    )
    assert bool(attack_instance.get("ignores_cover", False)) is True


def test_kaleidoscopic_tempest_queues_grants_stealth_and_flow_cover():
    game, ts_player, enemy_player, ts_army, enemy_army = _build_game()
    target = _make_unit(
        "Infernal Master",
        keywords=["THOUSAND SONS", "PSYKER", "INFANTRY"],
        faction_keywords=["THOUSAND SONS"],
    )
    attacker = _make_unit(
        "Enemy Shooters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    ts_army.add_unit(target)
    enemy_army.add_unit(attacker)
    _refresh(game, ts_player, enemy_player)
    _deploy_unit(game, target, 15.0, 10.0)
    _deploy_unit(game, attacker, 24.0, 10.0)
    _add_objective(game, ts_player, x=15.0, y=10.0, name="Center")

    _set_phase(game, enemy_player, "SHOOTING_PHASE", 1)
    game.event_system.publish("shooting_targets_selected", attacking_unit=attacker, target_units=[target])
    pending = _pending_by_name(ts_player.stratagems, "KALEIDOSCOPIC TEMPEST")
    assert len(pending) == 1

    ok = ts_player.stratagems.use(
        "KALEIDOSCOPIC TEMPEST",
        unit=target,
        attacking_unit=attacker,
        target_units=[target],
        phase_name="Shooting phase",
        dequeue=True,
    )

    assert ok is True
    assert int(ts_player.command_points or 0) == 9
    assert bool(target.special_rules.get("opponent_shooting_phase_stealth_active")) is True
    assert target.has_stealth() is True
    assert len(list((target.special_rules or {}).get("defensive_cover_bonuses", []) or [])) == 1

    game.event_system.publish("phase_end", player=enemy_player, phase=BattleRoundPhases.SHOOTING_PHASE)
    assert bool(target.special_rules.get("opponent_shooting_phase_stealth_active")) is False
    assert target.has_stealth() is False
    assert not list((target.special_rules or {}).get("defensive_cover_bonuses", []) or [])


def test_wrath_of_the_doomed_queues_and_threshold_changes_with_flow():
    outside_game, outside_player, outside_enemy_player, outside_army, outside_enemy_army = _build_game()
    outside_target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "INFANTRY", "RUBRICAE", "RUBRIC MARINES"],
        faction_keywords=["THOUSAND SONS"],
    )
    outside_attacker = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    outside_army.add_unit(outside_target)
    outside_enemy_army.add_unit(outside_attacker)
    _refresh(outside_game, outside_player, outside_enemy_player)
    _deploy_unit(outside_game, outside_target, 25.0, 10.0)
    _deploy_unit(outside_game, outside_attacker, 20.0, 10.0)

    _set_phase(outside_game, outside_enemy_player, "FIGHT_PHASE", 1)
    outside_game.event_system.publish("fight_targets_selected", attacking_unit=outside_attacker, target_units=[outside_target])
    assert _pending_by_name(outside_player.stratagems, "WRATH OF THE DOOMED")

    outside_ok = outside_player.stratagems.use(
        "WRATH OF THE DOOMED",
        unit=outside_target,
        attacking_unit=outside_attacker,
        target_units=[outside_target],
        phase_name="Fight phase",
        dequeue=True,
    )

    assert outside_ok is True
    outside_rule = outside_target.get_melee_fight_on_death_after_attacks_rule(model=outside_target.models[0])
    assert int(outside_rule.get("threshold", 0) or 0) == 4

    flow_game, flow_player, flow_enemy_player, flow_army, flow_enemy_army = _build_game()
    flow_target = _make_unit(
        "Rubric Marines",
        keywords=["THOUSAND SONS", "INFANTRY", "RUBRICAE", "RUBRIC MARINES"],
        faction_keywords=["THOUSAND SONS"],
    )
    flow_attacker = _make_unit(
        "Enemy Fighters",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    flow_army.add_unit(flow_target)
    flow_enemy_army.add_unit(flow_attacker)
    _refresh(flow_game, flow_player, flow_enemy_player)
    _deploy_unit(flow_game, flow_target, 15.0, 10.0)
    _deploy_unit(flow_game, flow_attacker, 24.0, 10.0)
    _add_objective(flow_game, flow_player, x=15.0, y=10.0, name="Center")

    _set_phase(flow_game, flow_enemy_player, "FIGHT_PHASE", 1)
    flow_game.event_system.publish("fight_targets_selected", attacking_unit=flow_attacker, target_units=[flow_target])
    assert _pending_by_name(flow_player.stratagems, "WRATH OF THE DOOMED")

    flow_ok = flow_player.stratagems.use(
        "WRATH OF THE DOOMED",
        unit=flow_target,
        attacking_unit=flow_attacker,
        target_units=[flow_target],
        phase_name="Fight phase",
        dequeue=True,
    )

    assert flow_ok is True
    flow_rule = flow_target.get_melee_fight_on_death_after_attacks_rule(model=flow_target.models[0])
    assert int(flow_rule.get("threshold", 0) or 0) == 3

    flow_game.event_system.publish("phase_end", player=flow_enemy_player, phase=BattleRoundPhases.FIGHT_PHASE)
    assert flow_target.get_melee_fight_on_death_after_attacks_rule(model=flow_target.models[0]) is None
