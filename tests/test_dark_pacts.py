import unittest
from types import SimpleNamespace

from warhammer40k_ai.classes.unit import Unit


class TestDarkPacts(unittest.TestCase):
    def test_dark_pacts_sets_choice(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "LETHAL HITS"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit.parent_army = army
        unit.possible_abilities = ["Dark Pacts"]
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = []
        unit.faction_keywords = []
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.pass_leadership_check = lambda: True

        unit.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")

        self.assertTrue(unit.special_rules.get("dark_pacts_active"))
        self.assertEqual(unit.special_rules.get("dark_pacts_choice"), "LETHAL HITS")
        self.assertEqual(unit.special_rules.get("dark_pacts_expires_phase"), "SHOOTING_PHASE")

    def test_dark_pacts_trigger_out_of_phase(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "SUSTAINED HITS 1"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit.parent_army = army
        unit.possible_abilities = ["Dark Pacts"]
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = []
        unit.faction_keywords = []
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.pass_leadership_check = lambda: True

        target = Unit.__new__(Unit)
        target.name = "Target"
        target.parent_army = p2.army

        game._on_shooting_targets_selected_dark_pacts(attacking_unit=unit, target_units=[target])

        self.assertTrue(unit.special_rules.get("dark_pacts_active"))
        self.assertEqual(unit.special_rules.get("dark_pacts_choice"), "SUSTAINED HITS 1")
        self.assertEqual(unit.special_rules.get("dark_pacts_expires_phase"), "MOVEMENT_PHASE")

    def test_dark_pacts_ignored_without_targets(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "LETHAL HITS"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="SHOOTING_PHASE")

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit.parent_army = army
        unit.possible_abilities = ["Dark Pacts"]
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = []
        unit.faction_keywords = []
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.pass_leadership_check = lambda: True

        game._on_shooting_targets_selected_dark_pacts(attacking_unit=unit, target_units=[])

        self.assertFalse(unit.special_rules.get("dark_pacts_active", False))

    def test_dark_pacts_ignore_fight_on_death_trigger(self):
        from warhammer40k_ai.classes.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.classes.player import Player, PlayerType
        from warhammer40k_ai.classes.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerType.HUMAN, army=army)
        p2 = Player("P2", PlayerType.AI, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "LETHAL HITS"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit.parent_army = army
        unit.possible_abilities = ["Dark Pacts"]
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = []
        unit.faction_keywords = []
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.pass_leadership_check = lambda: True

        unit.maybe_trigger_dark_pacts(game, phase_name="FIGHT_PHASE", trigger="fight_on_death")

        self.assertFalse(unit.special_rules.get("dark_pacts_active", False))


if __name__ == "__main__":
    unittest.main()
