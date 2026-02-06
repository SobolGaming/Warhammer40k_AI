import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class TestDarkPacts(unittest.TestCase):
    def test_dark_pacts_sets_choice(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "LETHAL HITS"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit._id = "Chosen"
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

        army.units.append(unit)
        game.rebuild_entity_registry()

        unit.maybe_trigger_dark_pacts(game, phase_name="SHOOTING_PHASE", trigger="shooting")

        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult

        req = game.decision_queue.peek()
        self.assertIsNotNone(req)
        option = next(opt for opt in req.options if opt.payload.get("choice") == "LETHAL HITS")
        result = DecisionResult(decision_id=req.decision_id, player_id=p1.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)

        self.assertTrue(unit.special_rules.get("dark_pacts_active"))
        self.assertEqual(unit.special_rules.get("dark_pacts_choice"), "LETHAL HITS")
        self.assertEqual(unit.special_rules.get("dark_pacts_expires_phase"), "SHOOTING_PHASE")

    def test_dark_pacts_trigger_out_of_phase(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "SUSTAINED HITS 1"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="MOVEMENT_PHASE")

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit._id = "Chosen"
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
        target._id = "Target"
        target.parent_army = p2.army

        army.units.append(unit)
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_dark_pacts(attacking_unit=unit, target_units=[target])

        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult

        req = game.decision_queue.peek()
        self.assertIsNotNone(req)
        option = next(opt for opt in req.options if opt.payload.get("choice") == "SUSTAINED HITS 1")
        result = DecisionResult(decision_id=req.decision_id, player_id=p1.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)

        self.assertTrue(unit.special_rules.get("dark_pacts_active"))
        self.assertEqual(unit.special_rules.get("dark_pacts_choice"), "SUSTAINED HITS 1")
        self.assertEqual(unit.special_rules.get("dark_pacts_expires_phase"), "MOVEMENT_PHASE")

    def test_dark_pacts_ignored_without_targets(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "LETHAL HITS"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="SHOOTING_PHASE")

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit._id = "Chosen"
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
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army("Other", "Other"))
        p1._next_optional_decisions = {"DARK_PACTS": True}
        p1._next_optional_selections = {"DARK_PACTS_CHOICE": "LETHAL HITS"}

        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])

        unit = Unit.__new__(Unit)
        unit.name = "Chosen"
        unit._id = "Chosen"
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

    def test_despoilers_dark_pact_grants_full_hit_reroll(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army("Other", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="SHOOTING_PHASE")

        unit = Unit.__new__(Unit)
        unit.name = "Chaos Terminators"
        unit._id = "CT"
        unit.parent_army = army
        unit.possible_abilities = ["Dark Pacts", "Despoilers"]
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = []
        unit.faction_keywords = []
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.pass_leadership_check = lambda: True

        army.units.append(unit)
        game.rebuild_entity_registry()

        applied = unit.apply_dark_pacts_choice(game, choice="LETHAL HITS", phase_name="SHOOTING_PHASE", trigger="shooting")
        self.assertTrue(applied)
        self.assertTrue(unit.special_rules.get("despoilers_active"))
        mods = unit.get_unit_hit_reroll_modifiers("ranged")
        self.assertTrue(mods.get("reroll_hit_full", False))

    def test_unholy_bloodshed_dark_pact_grants_devastating_wounds(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army
        from types import SimpleNamespace

        army = Army("Chaos Space Marines", detachment_type="Other")
        army.faction_id = "CSM"
        enemy_army = Army("Other", "Other")
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=enemy_army)
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="FIGHT_PHASE")

        unit = Unit.__new__(Unit)
        unit.name = "Possessed"
        unit._id = "POS"
        unit.parent_army = army
        unit.possible_abilities = ["Dark Pacts", "Unholy Bloodshed"]
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
        target._id = "TGT"
        target.parent_army = enemy_army
        target.keywords = []
        target.faction_keywords = []
        target.special_rules = {}
        target.round_state = SimpleNamespace()
        target.models = []

        army.units.append(unit)
        enemy_army.units.append(target)
        game.rebuild_entity_registry()

        applied = unit.apply_dark_pacts_choice(game, choice="LETHAL HITS", phase_name="FIGHT_PHASE", trigger="fight")
        self.assertTrue(applied)
        bonuses = unit.get_attack_keyword_bonuses(target=target, attack_type="melee")
        self.assertTrue(bonuses.get("devastating_wounds", False))


if __name__ == "__main__":
    unittest.main()
