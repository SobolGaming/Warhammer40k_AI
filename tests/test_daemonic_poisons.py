import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _UnitStub:
    def __init__(self, unit_id: str, name: str, army=None):
        self._id = unit_id
        self.name = name
        self.special_rules = {}
        self._army = army
        self.mortal_wounds_received = 0

    def get_parent_army(self):
        return self._army

    def get_attached_unit_root(self):
        return self

    def get_attached_unit_members(self):
        return []

    def _apply_mortal_wounds_to_unit(self, target_unit, amount, game_map=None):
        self.mortal_wounds_received += int(amount)


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
        self.last_roll_request = None

    def request_dice_roll(self, *, player_id, spec, prompt=None):
        self.last_roll_request = {"player_id": player_id, "spec": dict(spec or {}), "prompt": prompt}
        return None


class TestDaemonicPoisons(unittest.TestCase):
    def test_daemonic_poisons_decision_applies(self):
        from warhammer40k_ai.engine.decision_dispatcher import dispatch_decision
        from warhammer40k_ai.engine.decision_kinds import DECISION_CHOOSE_DAEMONIC_POISONS_TARGET
        from warhammer40k_ai.engine.decisions import DecisionOption, DecisionRequest, DecisionResult

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player)
        attacker = _UnitStub("ATK", "Attacker", army=army)
        target = _UnitStub("TGT", "Target", army=SimpleNamespace(player=SimpleNamespace(id="P2")))
        model = _ModelStub("M1", "Fulgrim")
        game = _GameStub(units=[attacker, target], models=[model], turn=2)

        option = DecisionOption.create("Target", payload={"unit_id": target._id})
        req = DecisionRequest.create(
            DECISION_CHOOSE_DAEMONIC_POISONS_TARGET,
            "Select Daemonic Poisons target.",
            player_id=player.id,
            options=[option],
            context={"attacker_unit_id": attacker._id, "model_id": model._id, "ability_name": "Daemonic Poisons"},
        )
        result = DecisionResult(decision_id=req.decision_id, player_id=player.id, option_id=option.option_id, payload={})
        apply_result = dispatch_decision(game, req, result)

        self.assertTrue(apply_result.ok)
        self.assertTrue(target.special_rules.get("daemonic_poisons_poisoned"))
        self.assertEqual(target.special_rules.get("daemonic_poisons_source"), "Daemonic Poisons")

    def test_daemonic_poisons_roll_handler_applies_mortal_wounds(self):
        from warhammer40k_ai.engine.roll_handlers import (
            handle_daemonic_poisons_roll,
            handle_daemonic_poisons_damage_roll,
        )
        from warhammer40k_ai.engine.dice_rolls import DiceRollState

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player)
        target = _UnitStub("U1", "Poisoned", army=army)
        game = _GameStub(units=[target], models=[])
        state = DiceRollState(roll_id=1, player_id=player.id, spec={"unit_id": target._id, "ability_name": "Daemonic Poisons"})
        state.total = 4

        dmg = handle_daemonic_poisons_roll(game, state)
        self.assertIsNone(dmg)
        self.assertIsNotNone(game.last_roll_request)
        self.assertEqual(game.last_roll_request["spec"].get("faces"), 3)
        self.assertEqual(game.last_roll_request["spec"].get("handler_key"), "daemonic_poisons_damage")

        damage_state = DiceRollState(
            roll_id=2,
            player_id=player.id,
            spec={"unit_id": target._id, "ability_name": "Daemonic Poisons"},
        )
        damage_state.total = 2
        dmg_applied = handle_daemonic_poisons_damage_roll(game, damage_state)
        self.assertEqual(dmg_applied, 2)
        self.assertEqual(target.mortal_wounds_received, 2)

        state_low = DiceRollState(roll_id=2, player_id=player.id, spec={"unit_id": target._id, "ability_name": "Daemonic Poisons"})
        state_low.total = 3
        dmg_low = handle_daemonic_poisons_roll(game, state_low)
        self.assertEqual(dmg_low, 0)
