import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER
from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult


class _UnitStub:
    def __init__(self, unit_id: str, name: str, *, army=None, keywords=None):
        self._id = unit_id
        self.name = name
        self._army = army
        self.keywords = list(keywords or [])
        self.faction_keywords = []
        self.special_rules = {}
        self.deployed = True
        self.is_embarked = False

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def is_alive(self):
        return True

    def has_any_keyword(self, keyword: str) -> bool:
        key = str(keyword or "").strip().upper()
        return key in {k.upper() for k in (self.keywords or [])}

    def _model_within_range_of_unit(self, model, target, range_value: float) -> bool:
        return True


class _ModelStub:
    def __init__(self, model_id: str, name: str, *, parent_unit=None, keywords=None):
        self._id = model_id
        self.name = name
        self.parent_unit = parent_unit
        self.keywords = list(keywords or [])
        self._temporary_effects = {}

    @property
    def is_alive(self) -> bool:
        return True

    def has_any_keyword(self, keyword: str) -> bool:
        key = str(keyword or "").strip().upper()
        return key in {k.upper() for k in (self.keywords or [])}


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


class TestHystericalFrenzyDecision(unittest.TestCase):
    def test_hysterical_frenzy_applies(self):
        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[])
        target = _UnitStub("TGT", "Daemonettes", army=army, keywords=["SLAANESH", "LEGIONES DAEMONICA"])
        psyker_unit = _UnitStub("PSY", "Tormentbringer", army=army)
        model = _ModelStub("M1", "Psyker", parent_unit=psyker_unit, keywords=["PSYKER"])
        game = _GameStub(units=[target, psyker_unit], models=[model])

        option = DecisionOption.create(
            "Psyker",
            payload={
                "model_id": model._id,
                "target_unit_id": target._id,
                "range": 6,
                "source_unit_id": psyker_unit._id,
            },
        )
        req = DecisionRequest.create(
            DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER,
            "Select a Psyker.",
            player_id=player.id,
            options=[DecisionOption.create("Decline", payload={"action": "skip"}), option],
            context={"ability_name": "Hysterical Frenzy", "target_unit_id": target._id},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertTrue(apply_result.ok)
        self.assertTrue(target.special_rules.get("hysterical_frenzy_active"))
        used = model._temporary_effects.get("hysterical_frenzy_used", {})
        self.assertEqual(used.get("expires_phase"), "FIGHT_PHASE")

    def test_hysterical_frenzy_invalid_option_rejected(self):
        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player, units=[])
        target = _UnitStub("TGT", "Daemonettes", army=army, keywords=["SLAANESH", "LEGIONES DAEMONICA"])
        psyker_unit = _UnitStub("PSY", "Tormentbringer", army=army)
        model = _ModelStub("M1", "Psyker", parent_unit=psyker_unit, keywords=["PSYKER"])
        game = _GameStub(units=[target, psyker_unit], models=[model])

        option = DecisionOption.create(
            "Psyker",
            payload={"model_id": model._id, "target_unit_id": target._id, "range": 6, "source_unit_id": psyker_unit._id},
        )
        req = DecisionRequest.create(
            DECISION_CHOOSE_HYSTERICAL_FRENZY_PSYKER,
            "Select a Psyker.",
            player_id=player.id,
            options=[option],
            context={"ability_name": "Hysterical Frenzy", "target_unit_id": target._id},
        )
        bad = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id="bad", payload={})
        apply_result = dispatch_decision(game, req, bad)
        self.assertFalse(apply_result.ok)


if __name__ == "__main__":
    unittest.main()
