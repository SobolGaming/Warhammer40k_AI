import unittest
from types import SimpleNamespace


class _UnitStub:
    def __init__(self, unit_id: str, army=None):
        self._id = unit_id
        self._army = army

    def get_parent_army(self):
        return self._army


class _RegistryStub:
    def __init__(self, unit):
        self._unit = unit

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit" and str(entity_id) == str(getattr(self._unit, "_id", "")):
            return self._unit
        return None


class _GameStub:
    def __init__(self, unit):
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.entity_registry = _RegistryStub(unit)
        self.decision_queue = DecisionQueue()
        self.is_authoritative = True


class _PowerFromPainStub:
    def __init__(self):
        self.calls = []

    def record_empowerment_choice(self, *, pending_key: str, choice_kind: str, choice: str, game=None):
        self.calls.append(
            {
                "pending_key": str(pending_key),
                "choice_kind": str(choice_kind),
                "choice": str(choice),
            }
        )
        return True


class TestPowerFromPainDecision(unittest.TestCase):
    def test_power_from_pain_choice_records(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POWER_FROM_PAIN_OPTION
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        mgr = _PowerFromPainStub()
        army = SimpleNamespace(player=player, power_from_pain=mgr)
        unit = _UnitStub("UNIT1", army=army)
        game = _GameStub(unit)

        option = DecisionOption.create(
            "Lethal Hits",
            payload={"unit_id": unit._id, "choice_kind": "archon_poisoned_tongue", "choice_key": "LETHAL"},
        )
        req = DecisionRequest.create(
            DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
            "Select Power from Pain option.",
            player_id=player.id,
            options=[option],
            context={"unit_id": unit._id, "choice_kind": "archon_poisoned_tongue", "pending_key": "PENDING1"},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertTrue(apply_result.ok)
        self.assertEqual(len(mgr.calls), 1)
        self.assertEqual(mgr.calls[0]["pending_key"], "PENDING1")
        self.assertEqual(mgr.calls[0]["choice_kind"], "archon_poisoned_tongue")
        self.assertEqual(mgr.calls[0]["choice"], "LETHAL")

    def test_power_from_pain_invalid_choice_rejected(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POWER_FROM_PAIN_OPTION
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        mgr = _PowerFromPainStub()
        army = SimpleNamespace(player=player, power_from_pain=mgr)
        unit = _UnitStub("UNIT1", army=army)
        game = _GameStub(unit)

        option = DecisionOption.create(
            "Lethal Hits",
            payload={"unit_id": unit._id, "choice_kind": "archon_poisoned_tongue", "choice_key": "LETHAL"},
        )
        req = DecisionRequest.create(
            DECISION_CHOOSE_POWER_FROM_PAIN_OPTION,
            "Select Power from Pain option.",
            player_id=player.id,
            options=[option],
            context={"unit_id": unit._id, "choice_kind": "archon_poisoned_tongue", "pending_key": "PENDING1"},
        )
        bad_result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id="bad", payload={})
        apply_result = dispatch_decision(game, req, bad_result)

        self.assertFalse(apply_result.ok)
