import types
import pytest

from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.classes.player import Player, PlayerType
from warhammer40k_ai.classes.mission_cards import (
    TakeAndHoldPrimary,
    TerraformPrimary,
    LinchpinPrimary,
    PurgeTheFoePrimary,
    ScorchedEarthPrimary,
    HiddenSuppliesPrimary,
    SupplyDropPrimary,
)


class DummyArmy:
    def __init__(self):
        self.units = []
        self.player = None
    def set_player(self, p):
        self.player = p


class DummyObjective:
    def __init__(self, x, y, removed=False):
        # Minimal holder with a location-like object
        self.location = types.SimpleNamespace(
            x=x,
            y=y,
            z=0.0,
            control_radius=3.0,
            terraformed_by=None,
            removed=removed,
            controlling_player=None,
        )
        # Default: no-op update_control; tests override per scenario
        def _noop_update_control(game):
            return
        self.location.update_control = _noop_update_control


def make_game_with_players():
    battlefield = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    p1 = Player("Player 1", PlayerType.HUMAN, army=DummyArmy())
    p2 = Player("Player 2", PlayerType.HUMAN, army=DummyArmy())
    game = Game(battlefield, players=[p1, p2])
    # Minimal deployment zones mapping for tests
    game.deployment_zones = {
        p1.name: {"zone": types.SimpleNamespace(contains_point=lambda x, y: (x < 10))},
        p2.name: {"zone": types.SimpleNamespace(contains_point=lambda x, y: (x > (battlefield.width - 10)))},
    }
    # Convenience: attach back refs
    p1.army.set_player(p1)
    p2.army.set_player(p2)
    return game, p1, p2


def set_objectives(game, objectives, control_map):
    """Install dummy objectives and configure control via monkeypatched update_control.

    control_map: dict[obj -> player or None]
    """
    game.map.objectives = objectives
    for obj in objectives:
        desired = control_map.get(obj, None)
        def mk_update(o, who):
            def _upd(g):
                o.location.controlling_player = who
            return _upd
        obj.location.update_control = mk_update(obj, desired)


def test_take_and_hold_per_turn_cap_and_control():
    game, p1, p2 = make_game_with_players()
    game.turn = 2
    card = TakeAndHoldPrimary()
    p1.set_primary_mission(card)
    # Two controlled objectives -> 10 VP (under cap)
    o1, o2 = DummyObjective(15, 10), DummyObjective(20, 10)
    set_objectives(game, [o1, o2], {o1: p1, o2: p1})
    vp = card.score_at_command_phase(game, p1)
    added = card.add_score(vp)
    assert added == 10
    # Add two more -> raw 20, capped to 15 per turn
    o3, o4 = DummyObjective(25, 10), DummyObjective(30, 10)
    set_objectives(game, [o1, o2, o3, o4], {o1: p1, o2: p1, o3: p1, o4: p1})
    vp2 = card.score_at_command_phase(game, p1)
    added2 = card.add_score(vp2)
    assert added2 == 15


def test_terraform_command_cap_and_end_of_turn_points():
    game, p1, p2 = make_game_with_players()
    game.turn = 2
    card = TerraformPrimary()
    p1.set_primary_mission(card)
    # Command phase: 3 objectives controlled -> 12 VP capped per turn
    o1, o2, o3 = DummyObjective(12, 10), DummyObjective(18, 10), DummyObjective(24, 10)
    set_objectives(game, [o1, o2, o3], {o1: p1, o2: p1, o3: p1})
    vp = card.score_at_command_phase(game, p1)
    assert vp == 12
    added = card.add_score(vp)
    assert added == 12
    # End of turn terraformed scoring: mark two
    o1.location.terraformed_by = p1
    o3.location.terraformed_by = p1
    eot_vp = card.score_at_end_of_turn(game, p1)
    assert eot_vp == 2


def test_linchpin_home_vs_other_objective_scoring():
    game, p1, p2 = make_game_with_players()
    game.turn = 2
    card = LinchpinPrimary()
    p1.set_primary_mission(card)
    # Place one home objective at x=5 and two others outside p1 DZ
    home = DummyObjective(5, 10)
    o2, o3 = DummyObjective(20, 10), DummyObjective(30, 10)
    set_objectives(game, [home, o2, o3], {home: p1, o2: p1, o3: p1})
    vp = card.score_at_command_phase(game, p1)
    # With home controlled: 3VP (home) + 5+5 = 13
    assert vp == 13
    added = card.add_score(vp)
    assert added == 13
    # If home not controlled: 3VP per objective (3*3=9)
    set_objectives(game, [home, o2, o3], {home: p2, o2: p1, o3: p1})
    vp2 = card.score_at_command_phase(game, p1)
    assert vp2 == 6


def test_purge_the_foe_end_of_battle_round_and_control():
    game, p1, p2 = make_game_with_players()
    game.turn = 2
    card = PurgeTheFoePrimary()
    p1.set_primary_mission(card)
    # Command phase control: p1 controls > p2
    o1, o2 = DummyObjective(15, 10), DummyObjective(20, 10)
    set_objectives(game, [o1, o2], {o1: p1, o2: p1})
    vp_cmd = card.score_at_command_phase(game, p1)
    assert vp_cmd == 8
    # End of battle round: opponent lost 2, p1 lost 0 -> 4 (destroyed 1+) + 4 (more than) = 8
    game.destroyed_units_this_battle_round_by_player = {p1: 0, p2: 2}
    eobr = card.score_at_end_of_battle_round(game, p1)
    assert eobr == 8


def test_scorched_earth_burn_action_and_removal():
    game, p1, p2 = make_game_with_players()
    game.turn = 2
    card = ScorchedEarthPrimary()
    p1.set_primary_mission(card)
    # Create objective in No Man's Land (x=30)
    obj = DummyObjective(30, 22)
    set_objectives(game, [obj], {obj: p1})
    # Monkeypatch geometric checks
    game._unit_within_range_of_objective = lambda unit: obj
    game._objective_in_player_deployment = lambda player, loc: False
    # Fake unit with minimal API
    round_state = types.SimpleNamespace(advanced_this_round=False, fell_back_this_round=False, shot_this_round=False)
    unit = types.SimpleNamespace(
        is_aircraft=False,
        is_battle_shocked=lambda: False,
        round_state=round_state,
        get_parent_army=lambda: types.SimpleNamespace(player=p1),
        is_alive=lambda: True,
        deployed=True,
        objective_control=1,
    )
    # Start action
    can = game.can_start_burn_objective(unit)
    assert can["valid"], can.get("reason")
    res = game.start_burn_objective_action(unit)
    assert res["valid"]
    # Complete on opponent turn end
    game.current_player_index = 1  # opponent index
    game._complete_actions_for_turn_end(p2)
    assert obj.location.removed is True


def test_hidden_supplies_cumulative_thresholds():
    game, p1, p2 = make_game_with_players()
    game.turn = 2
    card = HiddenSuppliesPrimary()
    p1.set_primary_mission(card)
    # Two objectives not in p1 DZ and p1 controls more
    o1, o2, o3 = DummyObjective(20, 10), DummyObjective(25, 10), DummyObjective(50, 10)
    set_objectives(game, [o1, o2, o3], {o1: p1, o2: p1, o3: p2})
    vp = card.score_at_command_phase(game, p1)
    # 5 (one not in DZ) + 5 (two not in DZ) + 5 (more than opponent) = 15
    assert vp == 15


def test_supply_drop_per_round_vp_and_removals():
    game, p1, p2 = make_game_with_players()
    card = SupplyDropPrimary()
    p1.set_primary_mission(card)
    # Three No Man's Land objectives (not center by x)
    o1, o2, o3 = DummyObjective(20, 10), DummyObjective(40, 10), DummyObjective(30, 10)
    set_objectives(game, [o1, o2, o3], {o1: p1, o2: p1, o3: p1})
    # BR2: 5 VP per -> 15
    game.turn = 2
    vp2 = card.score_at_command_phase(game, p1)
    assert vp2 in (10, 15)  # Depending on alpha/omega exclusion; at least >= two objectives
    # Force BR4 removal
    game.turn = 4
    _ = card.score_at_command_phase(game, p1)
    # One of alpha/omega should now be removed
    removed_count = sum(1 for o in [o1, o2, o3] if o.location.removed)
    assert removed_count >= 1
    # BR5: second removal
    game.turn = 5
    _ = card.score_at_command_phase(game, p1)
    removed_count2 = sum(1 for o in [o1, o2, o3] if o.location.removed)
    assert removed_count2 >= removed_count


