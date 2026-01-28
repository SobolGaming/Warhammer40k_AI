import unittest
from types import SimpleNamespace


def _build_game():
    from warhammer40k_ai.engine.game import Battlefield, BattlefieldSize, Game
    from warhammer40k_ai.roster.army import Army
    from warhammer40k_ai.roster.player import Player, PlayerControl

    bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
    game = Game(bf)

    army1 = Army("Aeldari", "Warhost")
    army2 = Army("Enemy", "Other")

    p1 = Player("P1", control=PlayerControl.LOCAL, army=army1)
    p2 = Player("P2", control=PlayerControl.REMOTE, army=army2)

    game.add_player(p1)
    game.add_player(p2)

    return game, p1, p2, army1, army2


class _MockDatasheet:
    def __init__(self, name, *, leadership="6"):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": str(leadership),
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


def _make_unit(name, *, leadership="6"):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, leadership=leadership)
    return Unit(datasheet)


class TestPostShootLeadershipDebuff(unittest.TestCase):
    def test_post_shoot_leadership_debuff_modifies_tests(self):
        from warhammer40k_ai.units import unit as unit_module

        target = _make_unit("Target", leadership="6")
        target.special_rules = {
            "post_shoot_leadership_debuff_active": True,
            "post_shoot_leadership_debuff_value": -1,
        }

        original_roll = unit_module.get_roll
        unit_module.get_roll = lambda _d: 7
        try:
            target.take_battle_shock_test(current_turn=1)
            self.assertFalse(target.is_battle_shocked())

            passed = target.pass_leadership_check()
            self.assertTrue(passed)
        finally:
            unit_module.get_roll = original_roll

    def test_post_shoot_leadership_debuff_clears_on_owner_shooting_phase(self):
        game, p1, _p2, army1, army2 = _build_game()
        target = _make_unit("Target", leadership="6")
        army2.add_unit(target)

        target.special_rules = {
            "post_shoot_leadership_debuff_active": True,
            "post_shoot_leadership_debuff_owner": p1.id,
            "post_shoot_leadership_debuff_turn": 1,
            "post_shoot_leadership_debuff_value": -1,
            "post_shoot_leadership_debuff_source": "Terrifying Crescendo",
        }

        game.phase = SimpleNamespace(name="SHOOTING_PHASE")
        game._on_phase_start_post_shoot_leadership_debuff_cleanup(player=p1, phase=game.phase)

        self.assertFalse(target.special_rules.get("post_shoot_leadership_debuff_active"))


if __name__ == "__main__":
    unittest.main()
