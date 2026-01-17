import unittest
from types import SimpleNamespace


class TestActsOfFaith(unittest.TestCase):
    def _make_army(self, faction_id: str, player):
        army = SimpleNamespace(faction_id=faction_id, units=[], player=player)
        return army

    def _make_unit(self, name: str, army, *, acts: bool = True, litany: bool = False, enhancement=None):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType

        abilities = []
        if acts:
            abilities.append(SimpleNamespace(name="Acts of Faith"))
        if litany:
            abilities.append(SimpleNamespace(name="Litany of Deeds"))

        class _Unit:
            def __init__(self):
                self.name = name
                self._id = name
                self.possible_abilities = list(abilities)
                self.enhancement = enhancement
                self.deployed = True
                self.embarked_in = None
                self.models = [
                    Model(
                        name=f"{name} model",
                        movement=6,
                        toughness=3,
                        save=3,
                        wounds=2,
                        leadership=7,
                        objective_control=1,
                        model_base=Base(BaseType.CIRCULAR, 1.0),
                    )
                ]
                for m in self.models:
                    m.parent_unit = self

            def get_parent_army(self):
                return army

            def get_attached_unit_root(self):
                return self

            def get_attached_unit_models(self):
                return list(self.models)

            def is_alive(self):
                return True

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() == "ADEPTA SORORITAS"

            @property
            def is_embarked(self):
                return self.embarked_in is not None

        return _Unit()

    def test_battle_round_gain(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(
            map=SimpleNamespace(roll_reroll_provider=lambda **_k: True),
            phase=SimpleNamespace(name="COMMAND_PHASE"),
        )
        player.game = game
        army = self._make_army("AS", player)
        mgr = aof.ActsOfFaithManager(army)

        seq = iter([5])
        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": next(seq)
        try:
            mgr.on_battle_round_start(1, game=game)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [5])

    def test_act_of_faith_once_per_phase(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        calls = {"count": 0}

        def _provider(**_kwargs):
            calls["count"] += 1
            return 6

        game = SimpleNamespace(
            map=SimpleNamespace(miracle_dice_provider=_provider),
            phase=SimpleNamespace(name="SHOOTING_PHASE"),
        )
        player = SimpleNamespace(name="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = self._make_army("AS", player)
        unit = self._make_unit("Sisters", army, acts=True)
        army.units.append(unit)

        mgr = aof.ActsOfFaithManager(army)
        mgr.miracle_dice = [6, 5]

        old_get_dice_roll = aof.get_dice_roll
        aof.get_dice_roll = lambda _faces=6: 2
        try:
            roll_1, _dice_1, used_1 = mgr.resolve_roll(unit, roll_type="hit", game=game, dice_count=1, die_faces=6)
            roll_2, _dice_2, used_2 = mgr.resolve_roll(unit, roll_type="hit", game=game, dice_count=1, die_faces=6)
        finally:
            aof.get_dice_roll = old_get_dice_roll

        self.assertTrue(used_1)
        self.assertFalse(used_2)
        self.assertEqual(roll_1, 6)
        self.assertEqual(roll_2, 2)
        self.assertEqual(mgr.miracle_dice, [5])
        self.assertEqual(calls["count"], 1)

    def test_litany_reroll_on_unit_destroyed(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=None, phase=SimpleNamespace(name="COMMAND_PHASE"))
        player.game = game
        army = self._make_army("AS", player)

        imagifier = self._make_unit("Imagifier", army, acts=False, litany=True)
        destroyed = self._make_unit("Battle Sisters", army, acts=True)
        army.units = [imagifier, destroyed]

        imagifier.models[0].set_location(0.0, 0.0, 0.0, 0.0)
        destroyed.models[0].set_location(6.0, 0.0, 0.0, 0.0)
        last_model = destroyed.models[0]

        mgr = aof.ActsOfFaithManager(army)

        seq = iter([2, 6])
        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": next(seq)
        try:
            mgr.on_unit_destroyed(destroyed, game=game, last_model=last_model)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [6])

    def test_charge_roll_uses_miracle(self):
        from warhammer40k_ai.engine.game import Game, Battlefield, BattlefieldSize
        from warhammer40k_ai.roster.player import Player, PlayerControl
        from warhammer40k_ai.units.unit import Unit
        from warhammer40k_ai.rules import acts_of_faith as aof

        class MockDatasheet:
            def __init__(self, name, model_count=1):
                self.name = name
                self.faction_data = {"name": "Adepta Sororitas"}
                self.keywords = []
                self.faction_keywords = ["ADEPTA SORORITAS"]
                self.datasheets_unit_composition = [{"description": f"{model_count} Test Model"}]
                self.datasheets_models_cost = [{"description": f"{model_count} models", "cost": 100}]
                self.datasheets_models = [{
                    "M": "6", "T": "3", "Sv": "3", "W": "1", "Ld": "7", "OC": "1",
                    "base_size": "32mm", "inv_sv": "7", "inv_sv_descr": "none",
                }]
                self.datasheets_wargear = []
                self.datasheets_options = [{"description": "none"}]
                self.datasheets_abilities = []
                self.loadout = "This model is equipped with: nothing"

        bf = Battlefield(BattlefieldSize.STRIKE_FORCE)
        game = Game(bf)
        p1 = Player("P1", control=PlayerControl.LOCAL, army=None)
        p2 = Player("P2", control=PlayerControl.REMOTE, army=None)
        game.add_player(p1)
        game.add_player(p2)
        p1.game = game

        charger = Unit(MockDatasheet("Charger"))
        target = Unit(MockDatasheet("Target"))
        charger.deployed = True
        target.deployed = True

        class _Army:
            def __init__(self, units, player):
                self.units = list(units)
                self.player = player
                self.faction_id = "AS"
                self.acts_of_faith = aof.ActsOfFaithManager(self)

            def on_battle_round_start(self, *_a, **_k):
                return None

        a1 = _Army([charger], p1)
        a2 = _Army([target], p2)
        p1.army = a1
        p2.army = a2
        charger.set_parent_army(a1)
        target.set_parent_army(a2)
        a1.acts_of_faith.miracle_dice = [6]

        if charger.models:
            charger.models[0].set_location(10, 10, 0, 0)
        if target.models:
            target.models[0].set_location(15, 10, 0, 0)

        game.map.miracle_dice_provider = lambda **_k: 6

        old_get_dice_roll = aof.get_dice_roll
        aof.get_dice_roll = lambda _faces=6: 1
        result = None
        try:
            result = game.declare_charge(charger, target)
        except Exception as exc:
            self.fail(f"declare_charge raised: {exc}")
        finally:
            aof.get_dice_roll = old_get_dice_roll

        self.assertIsNotNone(result, "Charge declaration failed; check distance/eligibility setup.")
        self.assertEqual(int(result.get("base_roll", 0)), 7)
        self.assertTrue(bool(result.get("miracle_used", False)))
        self.assertEqual(a1.acts_of_faith.miracle_dice, [])


if __name__ == "__main__":
    unittest.main()
