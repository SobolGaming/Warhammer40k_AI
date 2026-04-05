import unittest
from types import SimpleNamespace


class _EventSystemStub:
    def publish(self, *_args, **_kwargs):
        return None


class _GameStub:
    def __init__(self, player):
        from warhammer40k_ai.engine.decisions import DecisionQueue
        from warhammer40k_ai.engine.dice_rolls import DiceRollManager

        self.turn = 1
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.is_authoritative = True
        self.auto_resolve_dice_rolls = False
        self.decision_queue = DecisionQueue()
        self.roll_manager = DiceRollManager()
        self.event_system = _EventSystemStub()
        self._player = player

    def request_decision(self, request):
        self.decision_queue.add(request)

    def request_dice_roll(self, *, player_id, spec, prompt=None):
        return self.roll_manager.request_roll(self, player_id=player_id, spec=spec, prompt=prompt)

    def get_current_player(self):
        return self._player


class TestBattleFocusAgileManeuverReroll(unittest.TestCase):
    def test_reactive_maneuver_roll_includes_reroll_rule(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.engine.decision_kinds import DECISION_REQUEST_DICE_ROLL

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[], faction_id="AE")
        unit = Unit.__new__(Unit)
        unit._id = "UNIT1"
        unit.name = "Guardians"
        unit.special_rules = {"bearer_unit_agile_maneuver_reroll": True}
        unit.possible_abilities = []
        unit.attached_leaders = []
        unit.can_be_attached_to = []
        unit.attached_to = None
        unit._ability_cache = {}
        unit.get_parent_army = lambda: army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_members = lambda: [unit]
        unit.leading_battle_focus_token_refund_specs = lambda: []
        unit.has_any_keyword = lambda kw: str(kw or "").strip().upper() == "ASURYANI"
        army.units = [unit]

        mgr = BattleFocusManager(army)
        army.battle_focus = mgr
        mgr.tokens = 1

        game = _GameStub(player)

        mgr.apply_reactive_maneuver(unit, mgr.MANEUVER_OPPORTUNITY, game)

        requests = list(game.decision_queue.list() or [])
        roll_requests = [req for req in requests if req.decision_type == DECISION_REQUEST_DICE_ROLL]
        self.assertEqual(len(roll_requests), 1)
        roll_req = roll_requests[0]
        roll_id = roll_req.context.get("roll_id")
        self.assertIsNotNone(roll_id)
        state = game.roll_manager.get_roll(int(roll_id))
        self.assertIsNotNone(state)
        reroll_rules = list(state.spec.get("reroll_rules", []) or [])
        action_ids = {rule.get("action_id") for rule in reroll_rules if isinstance(rule, dict)}
        self.assertIn("reroll_agile_maneuver", action_ids)
        self.assertTrue(unit.special_rules.get("battle_focus_reactive_move_pending"))


if __name__ == "__main__":
    unittest.main()
