import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class TestAeldariMantleOfWisdom(unittest.TestCase):
    def _make_unit(self, army, *, name="Unit", keywords=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = list(keywords or [])
        unit.faction_keywords = ["Aeldari"]
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.possible_abilities = []
        unit._ability_cache = {"unit_attack_roll_rules": []}
        return unit

    def test_mantle_of_wisdom_applies_both_rerolls(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army

        army = Army.with_detachment("Aeldari", detachment_type="Aspect Host")
        army.faction_id = "AE"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army.with_detachment("Other", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="SHOOTING_PHASE")

        bodyguard = self._make_unit(army, name="Dire Avengers", keywords=["Aspect Warriors"])
        leader = self._make_unit(army, name="Autarch", keywords=["Character"])
        leader.special_rules = {"enhancement_mantle_of_wisdom": True}
        leader.attached_to = bodyguard
        bodyguard.attached_leaders = [leader]

        target = self._make_unit(p2.army, name="Target", keywords=["Infantry"])

        army.units.extend([bodyguard, leader])
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_path_of_warrior(attacking_unit=bodyguard, target_units=[target])

        self.assertIsNone(game.decision_queue.peek())
        self.assertEqual(bodyguard.special_rules.get("path_of_warrior_choice"), "BOTH")
        self.assertEqual(bodyguard.special_rules.get("path_of_warrior_expires_phase"), "SHOOTING_PHASE")


if __name__ == "__main__":
    unittest.main()
