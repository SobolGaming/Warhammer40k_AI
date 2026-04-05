import unittest


class TestNoPreyCanEvadeRerolls(unittest.TestCase):
    def test_advance_reroll_provider_updates_advance_roll_and_locks_command_reroll(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        class MockDatasheet:
            def __init__(self, name):
                self.name = name
                self.faction_data = {"name": "Test"}
                self.keywords = []
                self.faction_keywords = []
                self.datasheets_unit_composition = [{"description": "1 Test Model"}]
                self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
                self.datasheets_models = [{
                    "M": "6", "T": "4", "Sv": "3", "W": "1", "Ld": "7", "OC": "1",
                    "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
                }]
                self.datasheets_wargear = []
                self.datasheets_options = [{"description": "none"}]
                self.datasheets_abilities = []
                self.loadout = "This model is equipped with: nothing"

        no_prey = Ability(
            name="No Prey Can Evade",
            faction_id="",
            description="You can re-roll Advance and Charge rolls made for this model.",
            type="Datasheet",
            parameter="",
            legend=None,
        )

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        g = Game(bf)

        u = Unit(MockDatasheet("Shalaxi"))
        u.possible_abilities = [no_prey]

        p1 = Player("P1", control=PlayerControl.LOCAL, army=None)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=None)
        g.add_player(p1)
        g.add_player(p2)

        # Minimal army wiring
        class _Army:
            def __init__(self, unit, player):
                self.units = [unit]
                self.player = player
                self.faction_id = "TEST"

            def get_army(self):
                return self

            def on_battle_round_start(self, *_a, **_k):
                return None

        army = _Army(u, p1)
        p1.army = army
        u.set_parent_army(army)
        p1.game = g

        # Provider always says "reroll"
        g.map.roll_reroll_provider = lambda **_k: True

        published = []
        orig_publish = g.event_system.publish

        def _cap(event_name: str, **kwargs):
            published.append((event_name, kwargs))
            return orig_publish(event_name, **kwargs)

        g.event_system.publish = _cap

        # Patch Unit.get_roll (imported into module)
        from warhammer40k_ai.units import unit as unit_mod
        seq = iter([2, 5])  # initial, reroll
        old_get_roll = unit_mod.get_roll
        unit_mod.get_roll = lambda _s: next(seq)
        try:
            r = u.prepare_advance()
        finally:
            unit_mod.get_roll = old_get_roll

        self.assertEqual(int(r), 5)
        self.assertEqual(int(u.round_state.advance_roll), 5)

        # Ensure the published roll_made reflects reroll_locked=True
        rm = [x for x in published if x[0] == "roll_made" and x[1].get("roll_type") == "advance"]
        self.assertTrue(rm, "Expected an advance roll_made publish")
        self.assertTrue(bool(rm[-1][1].get("reroll_locked", False)))


if __name__ == "__main__":
    unittest.main()


