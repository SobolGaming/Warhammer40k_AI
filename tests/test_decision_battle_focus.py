import unittest
from types import SimpleNamespace


class _UnitStub:
    def __init__(self, *, army=None):
        self._id = "UNIT1"
        self.name = "Guardians"
        self.special_rules = {}
        self.keywords = ["ASURYANI"]
        self.possible_abilities = []
        self._army = army

    def get_parent_army(self):
        return self._army

    def has_any_keyword(self, keyword: str) -> bool:
        return str(keyword or "").strip().upper() in {k.upper() for k in self.keywords}


class _RegistryStub:
    def __init__(self, unit):
        self._unit = unit

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit" and str(entity_id) == str(getattr(self._unit, "_id", "")):
            return self._unit
        return None


class _GameStub:
    def __init__(self, player, unit):
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.turn = 1
        self.phase = SimpleNamespace(name="MOVEMENT_PHASE")
        self.is_authoritative = True
        self.decision_queue = DecisionQueue()
        self.entity_registry = _RegistryStub(unit)
        self._player = player

    def get_current_player(self):
        return self._player

    def request_decision(self, request):
        self.decision_queue.add(request)


class TestBattleFocusDecision(unittest.TestCase):
    def test_battle_focus_move_maneuver_decision_applies(self):
        from warhammer40k_ai.rules.battle_focus import BattleFocusManager
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER
        from warhammer40k_ai.engine.decisions import DecisionResult

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[], faction_id="AE")
        unit = _UnitStub(army=army)
        army.units = [unit]
        mgr = BattleFocusManager(army)
        army.battle_focus = mgr
        mgr.tokens = 1

        game = _GameStub(player, unit)

        mgr.maybe_trigger_move_maneuvers(unit, action="move", game=game)
        pending = list(game.decision_queue.list() or [])
        self.assertEqual(len(pending), 1)
        req = pending[0]
        self.assertEqual(req.decision_type, DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER)

        chosen = None
        for opt in req.options:
            if str(opt.payload.get("choice_key", "")) == mgr.MANEUVER_FLITTING:
                chosen = opt
                break
        self.assertIsNotNone(chosen)

        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=chosen.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)
        self.assertTrue(apply_result.ok)
        self.assertTrue(unit.special_rules.get("battle_focus_flitting_shadows_no_overwatch"))
        self.assertEqual(mgr.tokens, 0)

    def test_battle_focus_invalid_choice_rejected(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[])
        unit = _UnitStub(army=army)
        army.units = [unit]
        game = _GameStub(player, unit)

        req = DecisionRequest.create(
            DECISION_CHOOSE_BATTLE_FOCUS_MANEUVER,
            "Select Battle Focus maneuver.",
            player_id=player.id,
            options=[DecisionOption.create("Skip", payload={"action": "skip", "unit_id": unit._id})],
            context={"unit_id": unit._id, "trigger": "move"},
        )
        bad = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id="bad", payload={})
        apply_result = dispatch_decision(game, req, bad)
        self.assertFalse(apply_result.ok)
