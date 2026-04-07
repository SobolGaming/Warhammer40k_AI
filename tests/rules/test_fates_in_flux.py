import pytest

from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
from warhammer40k_ai.roster.player import Player, PlayerControl
from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.units.unit import Unit


class MockDatasheet:
    def __init__(self, name: str, *, faction_name: str = "Chaos Daemons", keywords=None):
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "6", "T": "4", "Sv": "3", "W": "1",
            "Ld": "7", "OC": "1",
            "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = []
        self.loadout = "This model is equipped with: nothing"


def _setup_game(
    *,
    detachment_p1: str = "Scintillating Legion",
    detachment_p2: str = "Other",
    p2_faction: str = "Opponents",
    p2_keywords=None,
):
    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    p1 = Player("P1", PlayerControl.LOCAL, None)
    p2 = Player("P2", PlayerControl.LOCAL, None)
    game.add_player(p1)
    game.add_player(p2)

    a1 = Army.with_detachment("Chaos Daemons", detachment_p1)
    a1.faction_id = "CD"
    a2 = Army.with_detachment(p2_faction, detachment_p2)
    if p2_faction == "Chaos Daemons":
        a2.faction_id = "CD"

    p1.set_army(a1)
    p2.set_army(a2)

    tz_unit = Unit(
        MockDatasheet(
            "Tzeentch Unit",
            faction_name="Chaos Daemons",
            keywords=["LEGIONES DAEMONICA", "TZEENTCH"],
        )
    )
    a1.add_unit(tz_unit)

    opp_unit = Unit(
        MockDatasheet(
            "Opponent Unit",
            faction_name=p2_faction,
            keywords=list(p2_keywords or []),
        )
    )
    a2.add_unit(opp_unit)

    game.rebuild_entity_registry()
    return game, p1, p2, tz_unit, opp_unit


def test_fates_in_flux_initial_tokens_and_transfer():
    game, p1, p2, _tz_unit, _opp_unit = _setup_game()
    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    assert mgr.tokens_for_player(p1) == 3
    assert mgr.tokens_for_player(p2) == 0
    assert mgr.spend_tokens(p1, 2, reason="test") is True
    assert mgr.tokens_for_player(p1) == 1
    assert mgr.tokens_for_player(p2) == 2


def test_fates_in_flux_command_phase_gain():
    game, p1, p2, _tz_unit, _opp_unit = _setup_game()
    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    mgr.tokens_by_player_id[str(p2.id)] = 1
    mgr.on_command_phase_start(game=game, player=p1)
    assert mgr.tokens_for_player(p1) == 4


def test_fates_in_flux_owner_requires_tzeentch():
    game, p1, _p2, tz_unit, _opp_unit = _setup_game()
    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    non_tz_unit = Unit(
        MockDatasheet(
            "Non-Tzeentch",
            faction_name="Chaos Daemons",
            keywords=["LEGIONES DAEMONICA", "KHORNE"],
        )
    )
    p1.army.add_unit(non_tz_unit)
    assert mgr.build_reroll_rule(game=game, player=p1, unit=non_tz_unit, roll_type="hit") is None
    rule = mgr.build_reroll_rule(game=game, player=p1, unit=tz_unit, roll_type="hit")
    assert rule is not None
    assert rule["action_id"] == "flux_reroll"
    assert rule["max_select"] == 3


def test_fates_in_flux_opponent_can_use_tokens():
    game, _p1, p2, _tz_unit, opp_unit = _setup_game()
    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    mgr.tokens_by_player_id[str(p2.id)] = 1
    rule = mgr.build_reroll_rule(game=game, player=p2, unit=opp_unit, roll_type="hit")
    assert rule is not None


def test_fates_in_flux_opponent_clause_ignored_with_mirror_detachments():
    game, _p1, p2, _tz_unit, opp_unit = _setup_game(
        detachment_p2="Scintillating Legion",
        p2_faction="Chaos Daemons",
        p2_keywords=["LEGIONES DAEMONICA", "KHORNE"],
    )
    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    mgr.tokens_by_player_id[str(p2.id)] = 1
    rule = mgr.build_reroll_rule(game=game, player=p2, unit=opp_unit, roll_type="hit")
    assert rule is None


def test_fates_in_flux_injects_advance_reroll_option():
    game, p1, _p2, tz_unit, _opp_unit = _setup_game()
    game.auto_resolve_dice_rolls = False
    mgr = game.fates_in_flux
    mgr.ensure_initialized(game)
    tz_unit.prepare_advance()
    roll_id = tz_unit.round_state.advance_roll_id
    assert roll_id is not None
    state = game.roll_manager.resolve_roll(game, int(roll_id))
    assert any(opt.get("action_id") == "flux_reroll" for opt in state.reroll_options)
