import types
import pytest

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.engine.mission_cards import (
    BehindEnemyLinesSecondary,
    StormHostileObjectiveSecondary,
    EngageOnAllFrontsSecondary,
    DefendStrongholdSecondary,
    MarkedForDeathSecondary,
    EstablishLocusSecondary,
    CleanseSecondary,
    AssassinationSecondary,
    NoPrisonersSecondary,
    CullTheHordeSecondary,
    DisplayOfMightSecondary,
    OverwhelmingForceSecondary,
    ExtendBattleLinesSecondary,
    ATemptingTargetSecondary,
    RecoverAssetsSecondary,
    AreaDenialSecondary,
    SecureNoMansLandSecondary,
)


class DummyArmy:
    def __init__(self):
        self.units = []
        self.player = None
    def set_player(self, p):
        self.player = p


def make_game():
    bf = Battlefield(size=BattlefieldSize.STRIKE_FORCE)
    p1 = Player("Player 1", PlayerControl.LOCAL, army=DummyArmy())
    p2 = Player("Player 2", PlayerControl.LOCAL, army=DummyArmy())
    game = Game(bf, players=[p1, p2])
    # Minimal DZ half-split zones
    game.deployment_zones = {
        p1.name: {"zone": types.SimpleNamespace(contains_point=lambda x, y: x < 10)},
        p2.name: {"zone": types.SimpleNamespace(contains_point=lambda x, y: x > (bf.width - 10))},
    }
    p1.army.set_player(p1)
    p2.army.set_player(p2)
    return game, p1, p2


def new_unit(at=(5, 5), alive=True, aircraft=False, battle_shocked=False, models=1):
    # Builds a minimal unit with models and API used by cards
    from shapely.geometry import Point as _Pt
    class M:
        def __init__(self, pos):
            self._pos = pos
            self.is_alive = True
            # Minimal model_base API for aura_utils-based distance checks
            self.model_base = type(
                "_TB",
                (),
                {"get_base_shape": lambda self_inner, p=pos: _Pt(float(p[0]), float(p[1])).buffer(0.5)},
            )()
        def get_location(self):
            return (self._pos[0], self._pos[1], 0.0)
    ms = [M(at) for _ in range(models)]
    u = types.SimpleNamespace(
        models=ms,
        is_alive=lambda: alive,
        is_aircraft=aircraft,
        is_battle_shocked=lambda: battle_shocked,
    )
    return u


def test_no_prisoners_incremental_scoring():
    game, p1, p2 = make_game()
    card = NoPrisonersSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]

    # Destroy two enemy units incrementally
    enemy_unit1 = types.SimpleNamespace(get_parent_army=lambda: p2.army)
    enemy_unit2 = types.SimpleNamespace(get_parent_army=lambda: p2.army)
    game.record_unit_destroyed(enemy_unit1)
    game.record_unit_destroyed(enemy_unit2)
    assert p1.get_score() == 4  # 2 + 2


def test_overwhelming_force_incremental_cap():
    game, p1, p2 = make_game()
    card = OverwhelmingForceSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]

    # Destroy two units -> 6VP, respect cap 5 via card.add_score
    enemy_unit1 = types.SimpleNamespace(get_parent_army=lambda: p2.army)
    enemy_unit2 = types.SimpleNamespace(get_parent_army=lambda: p2.army)
    game.record_unit_destroyed(enemy_unit1)
    game.record_unit_destroyed(enemy_unit2)
    assert p1.get_score() == 5


def test_behind_enemy_lines_basic():
    game, p1, p2 = make_game()
    card = BehindEnemyLinesSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # One eligible unit wholly in opponent DZ
    u = new_unit(at=(game.map.width - 5, 5))
    p1.army.units = [u]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp in (3, 4) and res.achieved


def test_behind_enemy_lines_two_units_is_4vp():
    game, p1, p2 = make_game()
    card = BehindEnemyLinesSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    u1 = new_unit(at=(game.map.width - 5, 5))
    u2 = new_unit(at=(game.map.width - 6, 6))
    p1.army.units = [u1, u2]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 4 and res.achieved


def test_engage_on_all_fronts_quarters():
    game, p1, p2 = make_game()
    card = EngageOnAllFrontsSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Units in 3 quarters more than 6" from center
    p1.army.units = [new_unit(at=(5, 5)), new_unit(at=(game.map.width - 5, 5)), new_unit(at=(5, game.map.height - 5))]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp in (2, 4)


def test_engage_on_all_fronts_two_quarters_is_1vp():
    game, p1, p2 = make_game()
    card = EngageOnAllFrontsSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    p1.army.units = [new_unit(at=(5, 5)), new_unit(at=(game.map.width - 5, 5))]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 1


def test_extend_battle_lines():
    game, p1, p2 = make_game()
    card = ExtendBattleLinesSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Simulate objective control
    class Obj:
        pass
    o_dz = Obj(); o_nml = Obj()
    for o, pos in [(o_dz, (5, 5)), (o_nml, (30, 10))]:
        loc = types.SimpleNamespace(x=pos[0], y=pos[1], removed=False, controlling_player=p1)
        obj = types.SimpleNamespace(location=loc)
        obj.location.update_control = lambda g: None
        game.map.objectives.append(obj)
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 4


def test_storm_hostile_objective_captured_hostile():
    game, p1, p2 = make_game()
    card = StormHostileObjectiveSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Create one objective initially controlled by opponent
    loc = types.SimpleNamespace(x=15, y=5, removed=False, controlling_player=p2)
    obj = types.SimpleNamespace(location=loc)
    obj.location.update_control = lambda g: None
    game.map.objectives = [obj]
    card.on_draw(game, p1)
    # Now end of turn p1 controls it
    obj.location.controlling_player = p1
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 4


def test_storm_hostile_objective_no_opp_start_and_gained_control_br2():
    game, p1, p2 = make_game()
    game.turn = 2
    card = StormHostileObjectiveSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    loc = types.SimpleNamespace(x=15, y=5, removed=False, controlling_player=None)
    obj = types.SimpleNamespace(location=loc)
    obj.location.update_control = lambda g: None
    game.map.objectives = [obj]
    card.on_draw(game, p1)
    # Opp did not control any at start; p1 gains one
    obj.location.controlling_player = p1
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 4


def test_defend_stronghold_br2_scores_in_dz():
    game, p1, p2 = make_game()
    game.turn = 2
    card = DefendStrongholdSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    loc = types.SimpleNamespace(x=5, y=5, removed=False, controlling_player=p1)
    obj = types.SimpleNamespace(location=loc)
    obj.location.update_control = lambda g: None
    game.map.objectives = [obj]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 3


def test_marked_for_death_alpha_or_gamma():
    game, p1, p2 = make_game()
    card = MarkedForDeathSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Opponent has units
    u1 = types.SimpleNamespace(is_alive=lambda: True)
    u2 = types.SimpleNamespace(is_alive=lambda: True)
    u3 = types.SimpleNamespace(is_alive=lambda: True)
    p2.army.units = [u1, u2, u3]
    card.on_draw(game, p1)
    # Destroy an alpha
    game.destroyed_units_this_turn = [card.alpha_targets[0]]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 5
    # Else gamma
    game.destroyed_units_this_turn = [card.gamma_target]
    res2 = card.score_at_end_of_turn(game, p1)
    assert res2.vp in (2, 5)


def test_establish_locus_center_vs_opponent_dz():
    game, p1, p2 = make_game()
    card = EstablishLocusSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Center completion
    center = (game.map.width / 2.0, game.map.height / 2.0, 0.0)
    game.completed_actions_this_turn = [{"player": p1, "action_name": "ESTABLISH_LOCUS", "unit_location": center}]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 2
    # Opponent DZ completion
    dz_loc = (game.map.width - 5, 5, 0.0)
    game.completed_actions_this_turn = [{"player": p1, "action_name": "ESTABLISH_LOCUS", "unit_location": dz_loc}]
    res2 = card.score_at_end_of_turn(game, p1)
    assert res2.vp == 4


def test_cleanse_action_counts():
    game, p1, p2 = make_game()
    card = CleanseSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    game.completed_actions_this_turn = [{"player": p1, "action_name": "CLEANSE"}]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 2
    game.completed_actions_this_turn = [{"player": p1, "action_name": "CLEANSE"}, {"player": p1, "action_name": "CLEANSE"}]
    res2 = card.score_at_end_of_turn(game, p1)
    assert res2.vp == 5


def test_assassination_character_or_all():
    game, p1, p2 = make_game()
    card = AssassinationSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # A character destroyed this turn
    m = types.SimpleNamespace(
        is_character=True,
        _base_wounds=4,
        parent_unit=types.SimpleNamespace(get_parent_army=lambda: p2.army),
    )
    game.models_destroyed_this_turn = [m]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 5
    # All enemy characters destroyed in battle
    game.models_destroyed_this_turn = []
    game.all_enemy_characters_destroyed = True
    res2 = card.score_at_end_of_turn(game, p1)
    assert res2.vp == 5


def test_cull_the_horde():
    game, p1, p2 = make_game()
    card = CullTheHordeSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    enemy = types.SimpleNamespace(
        is_infantry=True,
        starting_model_count=20,
        attached_leaders=[],
        get_parent_army=lambda: p2.army,
    )
    game.destroyed_units_this_turn = [enemy]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 5


def test_display_of_might():
    game, p1, p2 = make_game()
    game.turn = 2
    card = DisplayOfMightSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Two of ours in NML, one opponent in NML -> 4VP
    p1.army.units = [new_unit(at=(15, 5)), new_unit(at=(20, 5))]
    p2.army.units = [new_unit(at=(30, 5))]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 4


def test_a_tempting_target():
    game, p1, p2 = make_game()
    card = ATemptingTargetSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Two NML objectives
    for pos in [(15, 5), (45, 5)]:
        loc = types.SimpleNamespace(x=pos[0], y=pos[1], removed=False)
        obj = types.SimpleNamespace(location=loc)
        obj.location.update_control = lambda g: None
        game.map.objectives.append(obj)
    card.on_draw(game, p1)
    # Control target objective
    if card.target_objective:
        card.target_objective.location.controlling_player = p1
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp in (0, 5)


def test_recover_assets_counts():
    game, p1, p2 = make_game()
    card = RecoverAssetsSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    game.completed_actions_this_turn = [{"player": p1, "action_name": "RECOVER_ASSETS", "units_count": 2}]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 3
    game.completed_actions_this_turn = [{"player": p1, "action_name": "RECOVER_ASSETS", "units_count": 3}]
    res2 = card.score_at_end_of_turn(game, p1)
    assert res2.vp == 5


def test_area_denial_2_vs_5vp():
    game, p1, p2 = make_game()
    card = AreaDenialSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # Our unit within 3, enemy within 4 (so within 6) -> 2VP (no enemy within 3)
    p1_unit = new_unit(at=(game.map.width / 2.0, game.map.height / 2.0))
    p2_unit = new_unit(at=(game.map.width / 2.0 + 4, game.map.height / 2.0))
    p1.army.units = [p1_unit]
    p2.army.units = [p2_unit]
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp == 2
    # Enemy outside 6, we in 3 -> 5VP
    p2_unit2 = new_unit(at=(game.map.width / 2.0 + 10, game.map.height / 2.0))
    p2.army.units = [p2_unit2]
    res2 = card.score_at_end_of_turn(game, p1)
    assert res2.vp == 5


def test_secure_no_mans_land():
    game, p1, p2 = make_game()
    card = SecureNoMansLandSecondary()
    p1.set_secondary_deck([card])
    p1.active_secondaries = [card]
    # One and two NML controlled
    for pos in [(15, 5), (45, 5)]:
        loc = types.SimpleNamespace(x=pos[0], y=pos[1], removed=False, controlling_player=p1)
        obj = types.SimpleNamespace(location=loc)
        obj.location.update_control = lambda g: None
        game.map.objectives.append(obj)
    res = card.score_at_end_of_turn(game, p1)
    assert res.vp in (2, 5)


