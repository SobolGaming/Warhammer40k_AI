import unittest
from types import SimpleNamespace

from warhammer40k_ai.classes.unit import Unit


class TestSeductiveGambit(unittest.TestCase):
    def _make_unit(self, army):
        class _Unit:
            def __init__(self):
                self.name = "Daemonettes"
                self.special_rules = {}
                self.parent_army = army
                self.keywords = ["SLAANESH"]

            def get_parent_army(self):
                return self.parent_army

            def has_any_keyword(self, keyword: str) -> bool:
                kw = (keyword or "").strip().upper()
                return kw and any(kw == k.upper() for k in (self.keywords or []))

        return _Unit()

    def test_seductive_gambit_sets_flag_on_charge(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army

        army = Army("Chaos Daemons", detachment_type="Legion of Excess")
        army.faction_id = "CD"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"SEDUCTIVE_GAMBIT": True}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        unit = self._make_unit(army)

        game.event_system.publish("unit_move_ended", unit=unit, action="charge")

        self.assertTrue(unit.special_rules.get("seductive_gambit_active"))
        self.assertEqual(unit.special_rules.get("seductive_gambit_expires_phase"), "FIGHT_PHASE")

    def test_seductive_gambit_disables_fight_first(self):
        unit = Unit.__new__(Unit)
        unit.special_rules = {"seductive_gambit_active": True}
        unit.round_state = SimpleNamespace(charged_this_round=True)
        unit.has_fight_first = lambda: True
        self.assertFalse(Unit.should_fight_first(unit))


if __name__ == "__main__":
    unittest.main()
