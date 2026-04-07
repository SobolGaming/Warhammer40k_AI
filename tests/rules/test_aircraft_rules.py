import math

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize, SetupPhase
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.engine.deployment import DeploymentManager
from warhammer40k_ai.battlefield.map import Map
from warhammer40k_ai.units.unit import Unit, MovementAction
from warhammer40k_ai.utility.calcs import (
    build_collision_trees,
    get_pivot_cost,
    get_validation_rules,
    is_position_valid_unified_detailed,
    MovementType,
)


class MockDatasheet:
    def __init__(self, name: str, *, keywords=None, abilities=None, move: str = "12", cost: int = 100, base_size: str = "32mm"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": cost}]
        self.datasheets_models = [{
            "M": move, "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": base_size, "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, keywords=None, abilities=None, move: str = "12", cost: int = 100, faction: str = "A") -> Unit:
    unit = Unit(MockDatasheet(name, keywords=keywords, abilities=abilities, move=move, cost=cost))
    unit.deployed = True
    unit.faction = faction
    return unit


def attach_to_armies(game_map: Map, units_a, units_b):
    army_a = Army.with_detachment("Army A", "Detachment A")
    army_b = Army.with_detachment("Army B", "Detachment B")
    for u in units_a:
        army_a.add_unit(u)
    for u in units_b:
        army_b.add_unit(u)
    game_map.units = list(units_a) + list(units_b)
    return army_a, army_b


def test_aircraft_start_in_reserves_and_promote_after_setup():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army.with_detachment("Army1", "Det1")
    a2 = Army.with_detachment("Army2", "Det2")
    p1.set_army(a1)
    p2.set_army(a2)

    aircraft = make_unit("Jet", keywords=["Aircraft", "Fly"])
    a1.add_unit(aircraft)

    manager = DeploymentManager(game)
    manager.attacker = p1
    manager.defender = p2

    deployment_results = {
        "reserves": {
            p1.id: {aircraft.id: "deploy"},
            p2.id: {},
        }
    }

    manager.set_reserves_status(deployment_results)
    assert aircraft.reserve_status == "reserves"
    assert getattr(aircraft, "_started_in_reserves", False) is True

    game.setup_phase = SetupPhase.RESOLVE_PREBATTLE_RULES
    game.advance_setup_phase()
    assert aircraft.reserve_status == "strategic_reserves"


def test_aircraft_not_counted_toward_strategic_cap():
    army = Army.with_detachment("ArmyA", "DetA", points_limit=2000)
    aircraft = make_unit("Airframe", keywords=["Aircraft", "Fly"], cost=500)
    ground = make_unit("Ground", keywords=["Infantry"], cost=500)
    filler_a = make_unit("Filler A", keywords=["Infantry"], cost=100)
    filler_b = make_unit("Filler B", keywords=["Infantry"], cost=100)
    army.add_unit(aircraft)
    army.add_unit(ground)
    army.add_unit(filler_a)
    army.add_unit(filler_b)

    decisions = {
        aircraft.id: "reserves",
        ground.id: "strategic_reserves",
    }
    status = army.validate_reserves_decisions(decisions)
    assert status["valid"] is True
    assert status["strategic_points"] == 500


def test_aircraft_only_normal_moves_and_minimum_move():
    game_map = Map(width=100, height=100)
    aircraft = make_unit("Flyer", keywords=["Aircraft", "Fly"])
    game_map.units = [aircraft]

    aircraft.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    start = aircraft.models[0].get_location()

    assert aircraft.remain_stationary() is False
    assert aircraft.advance((10.0, 30.0, 0.0), game_map) is False
    assert aircraft.fall_back((10.0, 30.0, 0.0), [], game_map) is False

    # Must move straight forward
    assert aircraft.move((12.0, 35.0, 0.0), game_map) is False
    # Must move at least 20"
    assert aircraft.move((10.0, 25.0, 0.0), game_map) is True

    assert aircraft.models[0].get_location() == start
    assert aircraft.reserve_status == "strategic_reserves"
    assert aircraft not in game_map.units


def test_aircraft_move_off_board_sends_to_strategic_reserves_next_turn():
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, None)
    game.add_player(p1)

    army = Army.with_detachment("ArmyA", "DetA")
    p1.set_army(army)

    aircraft = make_unit("Bomber", keywords=["Aircraft", "Fly"])
    army.add_unit(aircraft)

    game_map = Map(width=30, height=30)
    game.map = game_map
    game_map.units = [aircraft]

    aircraft.models[0].set_location(10.0, 15.0, 0.0, 0.0)
    assert aircraft.move((10.0, 20.0, 0.0), game_map) is True

    assert aircraft.reserve_status == "strategic_reserves"
    assert aircraft not in game_map.units
    assert getattr(aircraft, "_aircraft_return_turn", None) == game.turn + 1


def test_aircraft_can_move_while_engaged():
    game_map = Map(width=100, height=100)
    aircraft = make_unit("Flyer", keywords=["Aircraft", "Fly"])
    enemy = make_unit("Enemy", keywords=["Infantry"], faction="B")
    attach_to_armies(game_map, [aircraft], [enemy])

    aircraft.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    enemy.models[0].set_location(12.0, 10.0, 0.0, 0.0)

    assert aircraft.move((10.0, 35.0, 0.0), game_map) is True
    assert aircraft.models[0].get_location()[1] > 10.0


def test_aircraft_post_move_pivot_is_applied_and_clamped():
    game_map = Map(width=100, height=100)
    aircraft = make_unit("Flyer", keywords=["Aircraft", "Fly"])
    game_map.units = [aircraft]

    aircraft.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    assert aircraft.move((10.0, 35.0, 0.0), game_map, aircraft_pivot_degrees=120.0) is True

    facing = float(getattr(aircraft.models[0].model_base, "facing", 0.0))
    assert math.isclose(facing, math.radians(90.0), abs_tol=1e-6)


def test_pivot_cost_vehicle_flying_base_over_32mm():
    vehicle = Unit(MockDatasheet("Skimmer", keywords=["Vehicle"], base_size="40mm flying base"))
    vehicle.deployed = True
    assert get_pivot_cost(vehicle) == 2


def test_engaged_only_by_aircraft_allows_normal_and_advance():
    game_map = Map(width=60, height=44)
    unit = make_unit("Infantry", keywords=["Infantry"])
    aircraft = make_unit("Enemy Jet", keywords=["Aircraft", "Fly"], faction="B")
    attach_to_armies(game_map, [unit], [aircraft])

    unit.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    aircraft.models[0].set_location(12.0, 10.0, 0.0, 0.0)

    state = unit.get_engagement_state(game_map)
    actions = unit.get_available_move_actions(state.value)

    assert MovementAction.MOVE.value in actions
    assert MovementAction.ADVANCE.value in actions


def test_aircraft_charge_and_fight_restrictions():
    game = Game(Battlefield(width=60, height=44))
    game_map = game.map
    aircraft = make_unit("Flyer", keywords=["Aircraft", "Fly"])
    non_fly = make_unit("Infantry", keywords=["Infantry"], faction="B")
    fly_unit = make_unit("Fly Unit", keywords=["Fly"], faction="B")
    attach_to_armies(game_map, [aircraft], [non_fly, fly_unit])

    aircraft.models[0].set_location(10.0, 10.0, 0.0, 0.0)
    non_fly.models[0].set_location(20.0, 10.0, 0.0, 0.0)
    fly_unit.models[0].set_location(21.0, 10.0, 0.0, 0.0)

    assert aircraft.can_declare_charge_against(non_fly, game) is False
    assert aircraft.charge_move((0.0, 0.0, 0.0), game_map) is False

    assert non_fly.can_declare_charge_against(aircraft, game) is False
    assert fly_unit.can_declare_charge_against(aircraft, game) is True

    non_fly.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    fly_unit.models[0].set_location(30.0, 30.0, 0.0, 0.0)

    assert aircraft.is_eligible_to_fight(game_map) is False
    assert non_fly.is_eligible_to_fight(game_map) is False

    fly_unit.models[0].set_location(12.0, 10.0, 0.0, 0.0)
    assert aircraft.is_eligible_to_fight(game_map) is True


def test_aircraft_engagement_range_rules_for_moves_and_charges():
    game_map = Map(width=60, height=44)
    mover = make_unit("Mover", keywords=["Infantry"], faction="A")
    flyer = make_unit("Flyer", keywords=["Fly"], faction="A")
    aircraft = make_unit("Enemy Aircraft", keywords=["Aircraft", "Fly"], faction="B")
    attach_to_armies(game_map, [mover, flyer], [aircraft])

    mover.models[0].set_location(5.0, 5.0, 0.0, 0.0)
    flyer.models[0].set_location(5.0, 7.0, 0.0, 0.0)
    aircraft.models[0].set_location(10.0, 10.0, 0.0, 0.0)

    target_pos = (12.0, 10.0, 0.0)

    trees = build_collision_trees(mover, MovementType.MOVE, game_map)
    rules = get_validation_rules(MovementType.MOVE, moving_unit=mover)
    res = is_position_valid_unified_detailed(
        target_pos, mover.models[0], trees, rules, game_map, is_final_position=True
    )
    assert res.get("valid") is False

    trees = build_collision_trees(flyer, MovementType.CHARGE, game_map)
    rules = get_validation_rules(MovementType.CHARGE, target_unit=aircraft, moving_unit=flyer)
    res = is_position_valid_unified_detailed(
        target_pos, flyer.models[0], trees, rules, game_map, is_final_position=True
    )
    assert res.get("valid") is True


def test_pile_in_excludes_aircraft_for_non_fly():
    from warhammer40k_ai.utility.calcs import MovementType as MT

    unit = make_unit("Infantry", keywords=["Infantry"])
    rules = get_validation_rules(MT.PILE_IN, moving_unit=unit)
    assert rules.get("closest_enemy_unit_exclude_keywords") == {"AIRCRAFT"}
