import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult


class _UnitStub:
    def __init__(self, unit_id: str, name: str, *, army=None):
        self._id = unit_id
        self.name = name
        self._army = army
        self.special_rules = {}

    def get_parent_army(self):
        return self._army

    def is_alive(self):
        return True


class _ModelStub:
    def __init__(self, model_id: str, name: str, *, parent_unit=None):
        self._id = model_id
        self.name = name
        self.parent_unit = parent_unit

    @property
    def is_alive(self) -> bool:
        return True


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
    def __init__(self, *, units, models):
        self.entity_registry = _RegistryStub(units=units, models=models)
        self.apply_calls = []

    def _apply_gift_of_chaos(self, *, source_unit, model, target_unit, ability_name: str, player):
        self.apply_calls.append(
            {
                "source_unit": source_unit,
                "model": model,
                "target_unit": target_unit,
                "ability_name": ability_name,
                "player": player,
            }
        )


class TestGiftOfChaosDecision(unittest.TestCase):
    def test_gift_of_chaos_applies(self):
        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[])
        enemy_army = SimpleNamespace(player=SimpleNamespace(id="P2"), units=[])
        attacker = _UnitStub("ATK", "Sorcerer", army=army)
        target = _UnitStub("TGT", "Target", army=enemy_army)
        model = _ModelStub("M1", "Sorcerer", parent_unit=attacker)
        game = _GameStub(units=[attacker, target], models=[model])

        option = DecisionOption.create(
            "Target",
            payload={"target_unit_id": target._id, "model_id": model._id, "attacker_unit_id": attacker._id},
        )
        req = DecisionRequest.create(
            DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET,
            "Select Gift of Chaos target.",
            player_id=player.id,
            options=[option],
            context={"ability_name": "Gift of Chaos", "model_id": model._id, "attacker_unit_id": attacker._id},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertTrue(apply_result.ok)
        self.assertEqual(len(game.apply_calls), 1)
        call = game.apply_calls[0]
        self.assertIs(call["source_unit"], attacker)
        self.assertIs(call["target_unit"], target)
        self.assertIs(call["model"], model)

    def test_gift_of_chaos_invalid_option_rejected(self):
        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[])
        attacker = _UnitStub("ATK", "Sorcerer", army=army)
        target = _UnitStub("TGT", "Target", army=SimpleNamespace(player=SimpleNamespace(id="P2"), units=[]))
        model = _ModelStub("M1", "Sorcerer", parent_unit=attacker)
        game = _GameStub(units=[attacker, target], models=[model])

        option = DecisionOption.create(
            "Target",
            payload={"target_unit_id": target._id, "model_id": model._id, "attacker_unit_id": attacker._id},
        )
        req = DecisionRequest.create(
            DECISION_CHOOSE_GIFT_OF_CHAOS_TARGET,
            "Select Gift of Chaos target.",
            player_id=player.id,
            options=[option],
            context={"ability_name": "Gift of Chaos", "model_id": model._id, "attacker_unit_id": attacker._id},
        )
        bad = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id="bad", payload={})
        apply_result = dispatch_decision(game, req, bad)
        self.assertFalse(apply_result.ok)


if __name__ == "__main__":
    unittest.main()
