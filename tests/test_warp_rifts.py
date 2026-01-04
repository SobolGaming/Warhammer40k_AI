import unittest

from warhammer40k_ai.classes.unit import Unit


class TestWarpRifts(unittest.TestCase):
    def _make_unit(self, army):
        unit = Unit.__new__(Unit)
        unit.parent_army = army
        unit.keywords = ["LEGIONES DAEMONICA"]
        unit.faction_keywords = []
        unit.possible_abilities = []
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.has_deep_strike = lambda: True
        return unit

    def test_warp_rifts_reduces_distance_in_shadow(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army

        army = Army("Chaos Daemons", detachment_type="Daemonic Incursion")
        army.faction_id = "CD"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game._unit_wholly_within_shadow_of_chaos = lambda _u: True

        unit = self._make_unit(army)
        self.assertEqual(game._warp_rifts_min_distance(unit), 6.0)

    def test_warp_rifts_defaults_to_nine(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army

        army = Army("Chaos Daemons", detachment_type="Daemonic Incursion")
        army.faction_id = "CD"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game._unit_wholly_within_shadow_of_chaos = lambda _u: False

        unit = self._make_unit(army)
        self.assertEqual(game._warp_rifts_min_distance(unit), 9.0)


if __name__ == "__main__":
    unittest.main()
