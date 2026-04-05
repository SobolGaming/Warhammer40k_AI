from __future__ import annotations

from types import SimpleNamespace

from warhammer40k_ai.battlefield.map import Objective, ObjectiveCategory, ObjectivePoint
from warhammer40k_ai.engine.game import BattleRoundPhases, Battlefield, BattlefieldSize, Game
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.rules.stratagem_descriptors import get_stratagem_tool_descriptor
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile


class _MockDatasheet:
    def __init__(
        self,
        name: str,
        *,
        faction_name: str = "Space Marines",
        keywords=None,
        faction_keywords=None,
        model_count: int = 1,
        wounds: int = 4,
    ):
        self.id = f"ds_{name.lower().replace(' ', '_')}"
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        if faction_keywords is None:
            faction_keywords = ["ADEPTUS ASTARTES"] if faction_name == "Space Marines" else [str(faction_name or "").upper()]
        self.faction_keywords = list(faction_keywords)
        self.datasheets_unit_composition = [{"description": f"{int(model_count)} Test Models"}]
        self.datasheets_models_cost = [{"description": f"{int(model_count)} models", "cost": 100}]
        self.datasheets_models = [
            {
                "name": "Test Model",
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": str(int(wounds)),
                "Ld": "7",
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
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
    faction_name: str = "Space Marines",
    keywords=None,
    faction_keywords=None,
    model_count: int = 1,
    wounds: int = 4,
) -> Unit:
    return Unit(
        _MockDatasheet(
            name,
            faction_name=faction_name,
            keywords=keywords,
            faction_keywords=faction_keywords,
            model_count=model_count,
            wounds=wounds,
        )
    )


def _build_game():
    game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
    game.turn = 1

    sm_army = Army("Space Marines", "1st Company Task Force")
    sm_army.faction_id = "SM"
    enemy_army = Army("Enemy", "Other")
    enemy_army.faction_id = "EN"

    sm_player = Player("Space Marines", control=PlayerControl.LOCAL, army=sm_army)
    enemy_player = Player("Enemy", control=PlayerControl.REMOTE, army=enemy_army)
    game.add_player(sm_player)
    game.add_player(enemy_player)

    sm_player.command_points = 10
    enemy_player.command_points = 10

    sm_army.configure_rule_managers(force=True)
    sm_player.stratagems.refresh_available()
    return game, sm_player, enemy_player, sm_army, enemy_army


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
    phase = SimpleNamespace(name=phase_name)
    game.phase = phase
    game.current_player_index = int(current_player_index)
    game.event_system.publish("phase_start", player=player, phase=phase)


def _pending_by_name(stratagems, name: str):
    target = str(name or "").strip().upper()
    for reaction in list(stratagems.get_pending_reactions() or []):
        if str(reaction.get("stratagem", "") or "").strip().upper() == target:
            return reaction
    return None


def _make_objective(name: str, x: float, y: float) -> Objective:
    point = ObjectivePoint(float(x), float(y), 0.0, control_radius=3.0)
    return Objective(
        name=name,
        category=ObjectiveCategory.PRIMARY,
        points=5,
        description="",
        conditions=lambda _game: False,
        location=point,
    )


def _make_profile(*, is_melee: bool, skill: str = "4+", strength: str = "4", damage: str = "1") -> WargearProfile:
    parent = SimpleNamespace(
        name="Test Weapon",
        is_melee=lambda: bool(is_melee),
        is_ranged=lambda: not bool(is_melee),
    )
    return WargearProfile(
        profile_name="Profile",
        wargear_data={
            "range": "Melee" if is_melee else "24",
            "A": "1",
            "BS_WS": str(skill),
            "S": str(strength),
            "AP": "0",
            "D": str(damage),
            "description": "",
        },
        parent_wargear=parent,
    )


def test_first_company_task_force_stratagem_descriptors_registered():
    expected = {
        "000008495005": ("Duty and Honour", "sticky_objective"),
        "000008495003": ("Heroes of the Chapter", "hit_bonus_and_conditional_wound_bonus"),
        "000008495007": ("Legendary Fortitude", "defensive_damage_reduction"),
        "000008495006": ("Orbital Teleportarium", "enter_strategic_reserves_with_temp_deep_strike"),
        "000008495004": ("Terrifying Proficiency", "delayed_enemy_battleshock_tests_with_conditional_modifier"),
    }
    for stratagem_id, (expected_name, expected_effect) in expected.items():
        by_id = get_stratagem_tool_descriptor(stratagem_id=stratagem_id, name=expected_name.upper())
        by_name = get_stratagem_tool_descriptor(name=expected_name.upper())
        assert by_id is not None
        assert by_name is not None
        assert by_id.name == expected_name
        assert by_name.name == expected_name
        assert by_id.effect == expected_effect


def test_duty_and_honour_reaction_applies_sticky_objective_control():
    game, sm_player, _enemy_player, sm_army, _enemy_army = _build_game()
    veterans = _make_unit(
        "Bladeguard Veteran Squad",
        keywords=["INFANTRY"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    objective = _make_objective("Home Objective", 10.0, 10.0)
    objective.location.controlling_player = sm_player
    sm_army.add_unit(veterans)
    _deploy_unit(game, veterans, 10.0, 10.0)
    game.map.objectives = [objective]
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "MOVEMENT_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "DUTY AND HONOUR")
    assert pending is not None

    ok = sm_player.stratagems.use("DUTY AND HONOUR", objective=objective, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert objective.location.sticky_controller is sm_player
    assert objective.location.controlling_player is sm_player


def test_heroes_of_the_chapter_applies_hit_bonus_and_conditional_wound_bonus_then_cleans_up():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    enemy = _make_unit(
        "Enemy Infantry",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    sm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 16.0, 10.0)
    game.rebuild_entity_registry()

    _set_phase(game, sm_player, "SHOOTING_PHASE", 0)
    pending = _pending_by_name(sm_player.stratagems, "HEROES OF THE CHAPTER")
    assert pending is not None

    ok = sm_player.stratagems.use("HEROES OF THE CHAPTER", dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    profile = _make_profile(is_melee=False, skill="4+", strength="4")
    attacker = terminators.models[0]
    hit_result = profile._hit_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("HEROES OF THE CHAPTER" in str(modifier).upper() for modifier in list(hit_result.get("modifiers", []) or []))

    wound_before = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("HEROES OF THE CHAPTER" in str(modifier).upper() for modifier in list(wound_before.get("modifiers", []) or []))

    attacker.take_damage(3, game_map=game.map)
    assert bool(terminators.is_below_half_strength())

    wound_after = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert any("HEROES OF THE CHAPTER" in str(modifier).upper() for modifier in list(wound_after.get("modifiers", []) or []))

    game.event_system.publish("phase_end", player=sm_player, phase=SimpleNamespace(name="SHOOTING_PHASE"))

    hit_after_cleanup = profile._hit_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    wound_after_cleanup = profile._wound_target_with_tracking(
        enemy,
        attacker,
        {"distance_to_target": 6.0},
        roll_value=4,
        allow_rerolls=False,
        log_roll=False,
    )
    assert not any("HEROES OF THE CHAPTER" in str(modifier).upper() for modifier in list(hit_after_cleanup.get("modifiers", []) or []))
    assert not any("HEROES OF THE CHAPTER" in str(modifier).upper() for modifier in list(wound_after_cleanup.get("modifiers", []) or []))

    terminators.round_state.fought_this_phase = False
    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    assert _pending_by_name(sm_player.stratagems, "HEROES OF THE CHAPTER") is not None


def test_legendary_fortitude_reaction_reduces_incoming_melee_damage():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    defenders = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    charger = _make_unit(
        "Enemy Chargers",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    sm_army.add_unit(defenders)
    enemy_army.add_unit(charger)
    _deploy_unit(game, defenders, 10.0, 10.0)
    _deploy_unit(game, charger, 12.0, 10.0)
    game.map.is_within_engagement_range = lambda first, second: {first, second} == {defenders, charger}
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "CHARGE_PHASE", 1)
    game.event_system.publish("unit_move_ended", unit=charger, action="charge")
    pending = _pending_by_name(sm_player.stratagems, "LEGENDARY FORTITUDE")
    assert pending is not None

    ok = sm_player.stratagems.use("LEGENDARY FORTITUDE", unit=defenders, attacking_unit=charger, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9

    game.phase = BattleRoundPhases.FIGHT_PHASE
    profile = _make_profile(is_melee=True, skill="3+", strength="6", damage="2")
    damage_result = profile._damage_target_with_tracking(
        defenders.models[0],
        charger.models[0],
        {"mortal_wound": False, "mortal_wound_in_addition": False},
    )
    assert int(damage_result.get("damage_applied", 0) or 0) == 1


def test_orbital_teleportarium_reaction_enters_reserves_with_next_movement_deep_strike():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
    )
    enemy = _make_unit(
        "Enemy Unit",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
    )
    sm_army.add_unit(terminators)
    enemy_army.add_unit(enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, enemy, 30.0, 10.0)
    game.map.is_within_engagement_range = lambda _first, _second: False
    game.rebuild_entity_registry()

    _set_phase(game, enemy_player, "FIGHT_PHASE", 1)
    game.event_system.publish("phase_end", player=enemy_player, phase=SimpleNamespace(name="FIGHT_PHASE"))
    pending = _pending_by_name(sm_player.stratagems, "ORBITAL TELEPORTARIUM")
    assert pending is not None

    ok = sm_player.stratagems.use("ORBITAL TELEPORTARIUM", unit=terminators, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert bool(terminators.is_in_strategic_reserves())

    sr = dict(getattr(terminators, "special_rules", {}) or {})
    assert bool(sr.get("midgame_temp_deep_strike"))
    assert str(sr.get("midgame_temp_deep_strike_turn_owner", "") or "") == str(sm_player.id or "")
    assert int(sr.get("midgame_temp_deep_strike_must_arrive_turn", 0) or 0) == 2

    game.turn = 2
    game.current_player_index = 0
    game.phase = BattleRoundPhases.MOVEMENT_PHASE
    assert bool(terminators.has_deep_strike())
    assert bool(terminators.can_arrive_from_reserves(game.turn))
    assert bool(terminators.must_arrive_from_reserves(game.turn))


def test_terrifying_proficiency_reaction_delays_then_forces_enemy_command_phase_tests():
    game, sm_player, enemy_player, sm_army, enemy_army = _build_game()
    terminators = _make_unit(
        "Terminator Squad",
        keywords=["INFANTRY", "TERMINATOR"],
        faction_keywords=["ADEPTUS ASTARTES"],
        wounds=4,
    )
    destroyed_enemy = _make_unit(
        "Destroyed Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    nearby_enemy = _make_unit(
        "Nearby Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    nearby_enemy.models[0].take_damage(3, game_map=None)
    full_enemy = _make_unit(
        "Full Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    far_enemy = _make_unit(
        "Far Enemy",
        faction_name="Enemy",
        keywords=["INFANTRY"],
        faction_keywords=["ENEMY"],
        wounds=4,
    )
    sm_army.add_unit(terminators)
    enemy_army.add_unit(destroyed_enemy)
    enemy_army.add_unit(nearby_enemy)
    enemy_army.add_unit(full_enemy)
    enemy_army.add_unit(far_enemy)
    _deploy_unit(game, terminators, 10.0, 10.0)
    _deploy_unit(game, destroyed_enemy, 30.0, 10.0)
    _deploy_unit(game, nearby_enemy, 15.0, 10.0)
    _deploy_unit(game, full_enemy, 14.5, 12.0)
    _deploy_unit(game, far_enemy, 30.0, 20.0)
    game.rebuild_entity_registry()

    terminators.round_state.charged_this_round = True
    _set_phase(game, sm_player, "FIGHT_PHASE", 0)
    game.event_system.publish("unit_destroyed", unit=destroyed_enemy, destroyed_by_unit=terminators)
    pending = _pending_by_name(sm_player.stratagems, "TERRIFYING PROFICIENCY")
    assert pending is not None

    ok = sm_player.stratagems.use("TERRIFYING PROFICIENCY", unit=terminators, dequeue=True)
    assert ok
    assert int(sm_player.command_points or 0) == 9
    assert bool(terminators.special_rules.get("space_marines_terrifying_proficiency_pending"))

    captures = {
        "nearby": {"calls": 0, "modifier": None, "reasons": []},
        "full": {"calls": 0, "modifier": None, "reasons": []},
        "far": {"calls": 0, "modifier": None, "reasons": []},
    }

    def _capture(target: Unit, key: str):
        original = target.take_battle_shock_test

        def _wrapped(*args, **kwargs):
            sr = dict(getattr(target, "special_rules", {}) or {})
            captures[key]["calls"] += 1
            captures[key]["modifier"] = int(sr.get("battle_shock_test_modifier", 0) or 0)
            captures[key]["reasons"] = list(sr.get("battle_shock_test_modifier_reasons", []) or [])
            return original(*args, **kwargs)

        target.take_battle_shock_test = _wrapped

    _capture(nearby_enemy, "nearby")
    _capture(full_enemy, "full")
    _capture(far_enemy, "far")

    _set_phase(game, enemy_player, "COMMAND_PHASE", 1)

    assert captures["nearby"]["calls"] == 1
    assert captures["full"]["calls"] == 1
    assert captures["far"]["calls"] == 0
    assert captures["nearby"]["modifier"] == -1
    assert any("Terrifying Proficiency" in str(reason) for reason in list(captures["nearby"]["reasons"] or []))
    assert captures["full"]["modifier"] == 0
    assert terminators.special_rules.get("space_marines_terrifying_proficiency_pending") is None
    assert nearby_enemy.special_rules.get("battle_shock_suppress_other_tests_phase") == "COMMAND_PHASE"
    assert full_enemy.special_rules.get("battle_shock_suppress_other_tests_phase") == "COMMAND_PHASE"
