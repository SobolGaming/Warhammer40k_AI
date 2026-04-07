import pytest
from types import SimpleNamespace


def test_cp_guardrail_allows_only_one_non_normal_cp_per_battle_round():
    from warhammer40k_ai.roster.player import Player, PlayerControl

    game = SimpleNamespace(turn=1)
    p = Player("P1", PlayerControl.LOCAL, None)
    p.set_game(game)
    p.command_points = 0

    # Normal command phase +1 does not count
    gained = p.gain_normal_command_phase_cp()
    assert gained == 1
    assert p.command_points == 1
    assert p.cp_gained_this_battle_round_excluding_normal_command_cp == 0

    # First non-normal CP gain is allowed (max +1 regardless of requested amount)
    gained = p.gain_command_points(2, reason="Test gain 2")
    assert gained == 1
    assert p.command_points == 2
    assert p.cp_gained_this_battle_round_excluding_normal_command_cp == 1

    # Second non-normal CP gain in same battle round is denied
    gained = p.gain_command_points(1, reason="Second gain")
    assert gained == 0
    assert p.command_points == 2

    # Next battle round resets the counter
    game.turn = 2
    gained = p.gain_command_points(1, reason="New battle round")
    assert gained == 1
    assert p.command_points == 3
    assert p.cp_gained_this_battle_round_excluding_normal_command_cp == 1


def test_command_phase_bonus_cp_is_subject_to_guardrail():
    from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
    from warhammer40k_ai.roster.player import Player, PlayerControl
    from warhammer40k_ai.roster.army import Army

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)
    game.turn = 1

    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.REMOTE, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army.with_detachment("Army1", "Det1")
    a2 = Army.with_detachment("Army2", "Det2")
    p1.set_army(a1)
    p2.set_army(a2)

    # Fake a deployed alive unit that grants +1 bonus CP in your command phase.
    u = type("U", (), {})()
    u._id = "u1"
    u.deployed = True
    u.reserve_status = "deployed"
    u.is_alive = lambda: True
    u.is_attached_leader = False
    u.is_below_half_strength = lambda: False
    u.take_battle_shock_test = lambda *_args, **_kwargs: None
    u.special_rules = {"command_phase_bonus_cp": 1}
    a1.units.append(u)

    # Spend the "one extra CP per battle round" elsewhere first.
    assert p1.gain_command_points(1, reason="Other bonus") == 1

    # Now start command phase: BOTH players gain normal CP, but P1's bonus CP should be denied by guardrail.
    game.current_player_index = 0
    before = p1.command_points
    before_p2 = p2.command_points
    game.start_command_phase()
    assert p1.command_points == before + 1  # normal CP
    assert p2.command_points == before_p2 + 1  # normal CP (non-active player also gains)


