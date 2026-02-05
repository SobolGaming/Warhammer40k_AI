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

    def _apply_mortal_wounds_to_unit(self, target_unit, amount, game_map=None):
        target_unit.mortal_wounds_received += int(amount)


class _ModelStub:
    def __init__(self, model_id: str, name: str):
        self._id = model_id
        self.name = name
        self.dead = False

    def die(self, game_map=None):
        self.dead = True


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
        self.map = None
        self.is_authoritative = True


class TestMalignSacrifice(unittest.TestCase):
    def test_malign_sacrifice_roll_applies_mortals_and_kills_model(self):
        from warhammer40k_ai.engine.dice_rolls import DiceRollState
        from warhammer40k_ai.engine.roll_handlers import handle_malign_sacrifice_roll

        player = SimpleNamespace(id="P1")
        army = SimpleNamespace(player=player)
        source = _UnitStub("SRC", "Apostles", army=army)
        target = _UnitStub("TGT", "Enemy", army=SimpleNamespace(player=SimpleNamespace(id="P2")))
        model = _ModelStub("M1", "Dark Disciple")
        game = _GameStub(units=[source, target], models=[model], turn=1)

        state = DiceRollState(
            roll_id=1,
            player_id=player.id,
            spec={
                "source_unit_id": source._id,
                "target_unit_id": target._id,
                "model_id": model._id,
                "ability_name": "Malign Sacrifice",
            },
        )
        state.total = 6

        with patch("warhammer40k_ai.utility.dice.get_roll", return_value=2):
            dmg = handle_malign_sacrifice_roll(game, state)

        self.assertEqual(dmg, 2)
        self.assertEqual(target.mortal_wounds_received, 2)
        self.assertTrue(model.dead)
