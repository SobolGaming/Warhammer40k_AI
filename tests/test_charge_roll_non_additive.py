import unittest


class TestChargeRollNonAdditive(unittest.TestCase):
    def _make_game(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)

        p1 = Player("P1", control=PlayerControl.LOCAL, army=None)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=None)
        game.add_player(p1)
        game.add_player(p2)
        p1.game = game
        p2.game = game
        return game, p1, p2

    def _make_unit(self, name: str):
        from warhammer40k_ai.units.unit import Unit

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

        unit = Unit(MockDatasheet(name))
        unit.deployed = True
        return unit

    def test_charge_roll_keeps_highest_two_of_three(self):
        game, p1, p2 = self._make_game()
        charger = self._make_unit("Charger")
        target = self._make_unit("Target")

        class _Army:
            def __init__(self, units, player):
                self.units = list(units)
                self.player = player
                self.faction_id = "TEST"

            def on_battle_round_start(self, *_a, **_k):
                return None

        a1 = _Army([charger], p1)
        a2 = _Army([target], p2)
        p1.army = a1
        p2.army = a2
        charger.set_parent_army(a1)
        target.set_parent_army(a2)

        charger.special_rules["charge_roll_dice_count"] = 3
        charger.special_rules["charge_roll_keep_highest"] = 2

        charger.models[0].set_location(10, 10, 0, 0)
        target.models[0].set_location(15, 10, 0, 0)
        game.map.units = [charger, target]

        published = []
        orig_publish = game.event_system.publish

        def _cap(event_name: str, **kwargs):
            published.append((event_name, kwargs))
            return orig_publish(event_name, **kwargs)

        game.event_system.publish = _cap
        declared = game.declare_charge(charger, target)

        self.assertIsNotNone(declared)
        dice = list(declared.get("dice") or [])
        self.assertEqual(len(dice), 3)
        expected = sum(sorted([int(d or 0) for d in dice], reverse=True)[:2])
        self.assertEqual(int(declared.get("base_roll")), expected)

        rm = [x for x in published if x[0] == "roll_made" and x[1].get("roll_type") == "charge"]
        self.assertTrue(rm, "Expected a charge roll_made publish")
        last = rm[-1][1]
        self.assertEqual(int(last.get("value")), expected)

    def test_charge_roll_max_distance_uses_dice_spec(self):
        game, p1, p2 = self._make_game()
        charger = self._make_unit("Charger")
        target = self._make_unit("Target")

        class _Army:
            def __init__(self, units, player):
                self.units = list(units)
                self.player = player
                self.faction_id = "TEST"

            def on_battle_round_start(self, *_a, **_k):
                return None

        a1 = _Army([charger], p1)
        a2 = _Army([target], p2)
        p1.army = a1
        p2.army = a2
        charger.set_parent_army(a1)
        target.set_parent_army(a2)

        charger.special_rules["charge_roll_dice_count"] = 3
        charger.special_rules["charge_roll_keep_highest"] = 3
        self.assertEqual(float(game.get_max_charge_distance(charger, target_unit=target)), 18.0)

        charger.special_rules["charge_roll_keep_highest"] = 2
        self.assertEqual(float(game.get_max_charge_distance(charger, target_unit=target)), 12.0)


if __name__ == "__main__":
    unittest.main()
