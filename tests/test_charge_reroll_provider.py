import unittest


class TestChargeRerollProvider(unittest.TestCase):
    def test_charge_reroll_is_applied_before_success_evaluation(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.units.ability import Ability

        class MockDatasheet:
            def __init__(self, name, model_count=1):
                self.name = name
                self.faction_data = {"name": "Test"}
                self.keywords = []
                self.faction_keywords = []
                self.datasheets_unit_composition = [{"description": f"{model_count} Test Model"}]
                self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
                self.datasheets_models = [{
                    "M": "6", "T": "4", "Sv": "3", "W": "1", "Ld": "7", "OC": "1",
                    "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
                }]
                self.datasheets_wargear = []
                self.datasheets_options = [{"description": "none"}]
                self.datasheets_abilities = []
                self.loadout = "This model is equipped with: nothing"

        reroll_charge = Ability(
            name="No Prey Can Evade",
            faction_id="",
            description="You can re-roll Advance and Charge rolls made for this model.",
            type="Datasheet",
            parameter="",
            legend=None,
        )

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        g = Game(bf)

        p1 = Player("P1", control=PlayerControl.LOCAL, army=None)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=None)
        g.add_player(p1)
        g.add_player(p2)
        p1.game = g

        u = Unit(MockDatasheet("Charger", model_count=1))
        u.possible_abilities = [reroll_charge]
        u.deployed = True
        t = Unit(MockDatasheet("Target", model_count=1))
        t.deployed = True

        # Minimal army wiring
        class _Army:
            def __init__(self, units, player):
                self.units = list(units)
                self.player = player
                self.faction_id = "TEST"

            def on_battle_round_start(self, *_a, **_k):
                return None

        a1 = _Army([u], p1)
        a2 = _Army([t], p2)
        p1.army = a1
        p2.army = a2
        u.set_parent_army(a1)
        t.set_parent_army(a2)

        # Positions close enough that a rerolled 12" would be sufficient; we won't actually move (charge_move patched)
        if u.models:
            u.models[0].set_location(10, 10, 0, 0)
        if t.models:
            t.models[0].set_location(15, 10, 0, 0)
        g.map.units = [u, t]

        # Provider always says "reroll"
        g.map.roll_reroll_provider = lambda **_k: True

        # Prevent movement complexity after a successful charge roll
        u.charge_move = lambda *_a, **_k: False

        published = []
        orig_publish = g.event_system.publish

        def _cap(event_name: str, **kwargs):
            published.append((event_name, kwargs))
            return orig_publish(event_name, **kwargs)

        g.event_system.publish = _cap
        _ = g.attempt_charge(u, t)

        rm = [x for x in published if x[0] == "roll_made" and x[1].get("roll_type") == "charge"]
        self.assertTrue(rm, "Expected a charge roll_made publish")
        last = rm[-1][1]
        dice = list(last.get("dice") or [])
        expected = sum(int(d or 0) for d in dice)
        self.assertEqual(int(last.get("value")), expected)
        self.assertTrue(bool(last.get("reroll_locked", False)))


if __name__ == "__main__":
    unittest.main()


