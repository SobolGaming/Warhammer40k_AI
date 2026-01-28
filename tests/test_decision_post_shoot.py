import unittest
from types import SimpleNamespace


class _UnitStub:
    def __init__(self, unit_id: str, name: str, army=None):
        self._id = unit_id
        self.name = name
        self.special_rules = {}
        self._army = army
        self.battleshock_turns = []

    def get_parent_army(self):
        return self._army

    def take_battle_shock_test(self, turn: int):
        self.battleshock_turns.append(int(turn))

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return []


class _ModelStub:
    def __init__(self, model_id: str, name: str):
        self._id = model_id
        self.name = name


class _RegistryStub:
    def __init__(self, *, units, models):
        self._units = {str(u._id): u for u in units}
        self._models = {str(m._id): m for m in models}

    def get(self, entity_id: str, *, kind: str):
        if kind == "unit":
            return self._units.get(str(entity_id))
        if kind == "model":
            return self._models.get(str(entity_id))
        return None


class _GameStub:
    def __init__(self, *, units, models, turn: int = 1):
        from warhammer40k_ai.engine.decisions import DecisionQueue

        self.turn = int(turn)
        self.entity_registry = _RegistryStub(units=units, models=models)
        self.decision_queue = DecisionQueue()
        self.is_authoritative = True


class TestPostShootDecisions(unittest.TestCase):
    def test_post_shoot_battleshock_applies(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player)
        attacker = _UnitStub("ATK", "Attacker", army=army)
        target = _UnitStub("TGT", "Target", army=SimpleNamespace(player=SimpleNamespace(id="P2")))
        model = _ModelStub("M1", "Shooter")
        game = _GameStub(units=[attacker, target], models=[model], turn=3)

        option = DecisionOption.create("Target", payload={"unit_id": target._id})
        req = DecisionRequest.create(
            DECISION_CHOOSE_POST_SHOOT_BATTLESHOCK_TARGET,
            "Select post-shoot Battle-shock target.",
            player_id=player.id,
            options=[option],
            context={"attacker_unit_id": attacker._id, "model_id": model._id, "ability_name": "Shock Pulse"},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertTrue(apply_result.ok)
        self.assertEqual(target.battleshock_turns, [3])

    def test_post_shoot_suppression_applies(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player)
        attacker = _UnitStub("ATK", "Attacker", army=army)
        target = _UnitStub("TGT", "Target", army=SimpleNamespace(player=SimpleNamespace(id="P2")))
        model = _ModelStub("M1", "Suppressor")
        game = _GameStub(units=[attacker, target], models=[model], turn=2)

        option = DecisionOption.create("Target", payload={"unit_id": target._id})
        req = DecisionRequest.create(
            DECISION_CHOOSE_POST_SHOOT_SUPPRESSION_TARGET,
            "Select suppression target.",
            player_id=player.id,
            options=[option],
            context={"attacker_unit_id": attacker._id, "model_id": model._id, "ability_name": "Suppressed"},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertTrue(apply_result.ok)
        self.assertTrue(target.special_rules.get("post_shoot_suppressed_active"))
        self.assertEqual(target.special_rules.get("post_shoot_suppressed_owner"), player.id)
        self.assertEqual(target.special_rules.get("post_shoot_suppressed_turn"), 2)
