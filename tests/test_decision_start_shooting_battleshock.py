import unittest
from types import SimpleNamespace


class _UnitStub:
    def __init__(self, unit_id: str, name: str, army=None):
        self._id = unit_id
        self.name = name
        self._army = army
        self.special_rules = {}

    def get_parent_army(self):
        return self._army

    def take_battle_shock_test(self, _turn: int):
        return None

    def is_alive(self):
        return True

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
        self.turn = int(turn)
        self.entity_registry = _RegistryStub(units=units, models=models)
        self.is_authoritative = True


class TestStartShootingBattleshockDecision(unittest.TestCase):
    def test_start_shooting_battleshock_requires_target(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player)
        attacker = _UnitStub("ATK", "Attacker", army=army)
        target = _UnitStub("TGT", "Target", army=SimpleNamespace(player=SimpleNamespace(id="P2")))
        model = _ModelStub("M1", "Caster")
        game = _GameStub(units=[attacker, target], models=[model], turn=1)

        option = DecisionOption.create("Invalid", payload={})
        req = DecisionRequest.create(
            DECISION_CHOOSE_START_SHOOTING_BATTLESHOCK_TARGET,
            "Select Battle-shock target.",
            player_id=player.id,
            options=[option],
            context={"model_id": model._id, "ability_name": "Sonic Fear"},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertFalse(apply_result.ok)
        self.assertIn("Start of Shooting phase Battle-shock requires target unit.", apply_result.errors)
