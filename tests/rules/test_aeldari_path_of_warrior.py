import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.unit import Unit


class TestAeldariPathOfWarrior(unittest.TestCase):
    def _make_unit(self, army, *, name="Aspect Warriors"):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = army
        unit.special_rules = {}
        unit.round_state = SimpleNamespace()
        unit.keywords = ["Aspect Warriors"]
        unit.faction_keywords = ["Aeldari"]
        unit.models = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit.attached_leaders = []
        unit.possible_abilities = []
        unit._ability_cache = {"unit_attack_roll_rules": []}
        return unit

    def test_path_of_warrior_choice_applies_hit_rerolls(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decisions import DecisionResult
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_PATH_OF_WARRIOR

        army = Army.with_detachment("Aeldari", detachment_type="Aspect Host")
        army.faction_id = "AE"
        p1 = Player("P1", PlayerControl.LOCAL, army=army)
        p2 = Player("P2", PlayerControl.REMOTE, army=Army.with_detachment("Other", "Other"))
        game = Game(Battlefield(size=BattlefieldSize.STRIKE_FORCE), players=[p1, p2])
        game.phase = SimpleNamespace(name="SHOOTING_PHASE")

        unit = self._make_unit(army, name="Howling Banshees")
        target = Unit.__new__(Unit)
        target.name = "Target"
        target._id = "Target"
        target.parent_army = p2.army

        army.units.append(unit)
        game.rebuild_entity_registry()

        game._on_shooting_targets_selected_path_of_warrior(attacking_unit=unit, target_units=[target])

        req = game.decision_queue.peek()
        self.assertIsNotNone(req)
        self.assertEqual(req.decision_type, DECISION_CHOOSE_PATH_OF_WARRIOR)
        option = next(opt for opt in req.options if opt.payload.get("choice_key") == "HIT")
        result = DecisionResult(decision_id=req.decision_id, player_id=p1.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)

        hit_mods = unit.get_unit_hit_reroll_modifiers("ranged")
        wound_mods = unit.get_unit_wound_reroll_modifiers("ranged")
        self.assertIn(1, hit_mods.get("reroll_hit_values", ()))
        self.assertNotIn(1, wound_mods.get("reroll_wound_values", ()))


if __name__ == "__main__":
    unittest.main()
