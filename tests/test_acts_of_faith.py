import unittest
from types import SimpleNamespace


class TestActsOfFaith(unittest.TestCase):
    def _make_army(self, faction_id: str, player, detachment_type: str = ""):
        army = SimpleNamespace(
            faction_id=faction_id,
            detachment_type=detachment_type,
            units=[],
            player=player,
            adepta_sororitas_detachments=None,
        )
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

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
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

    def test_solemn_procession_forces_battle_round_miracle_die_to_six(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=SimpleNamespace(), phase=SimpleNamespace(name="COMMAND_PHASE"))
        player.game = game
        army = self._make_army("AS", player)
        triumph = self._make_unit("Triumph Of Saint Katherine", army, acts=True)
        triumph.possible_abilities.append(SimpleNamespace(name="Solemn Procession"))
        army.units = [triumph]
        mgr = aof.ActsOfFaithManager(army)

        calls = {"count": 0}
        old_get_roll = aof.get_roll

        def _get_roll(_s="D6"):
            calls["count"] += 1
            return 2

        aof.get_roll = _get_roll
        try:
            mgr.on_battle_round_start(1, game=game)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(calls["count"], 0)
        self.assertEqual(mgr.miracle_dice, [6])

    def test_solemn_procession_does_not_apply_when_source_not_on_battlefield(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=SimpleNamespace(), phase=SimpleNamespace(name="COMMAND_PHASE"))
        player.game = game
        army = self._make_army("AS", player)
        triumph = self._make_unit("Triumph Of Saint Katherine", army, acts=True)
        triumph.possible_abilities.append(SimpleNamespace(name="Solemn Procession"))
        triumph.embarked_in = object()
        army.units = [triumph]
        mgr = aof.ActsOfFaithManager(army)

        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": 4
        try:
            mgr.on_battle_round_start(1, game=game)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [4])

    def test_act_of_faith_once_per_phase(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        calls = {"count": 0}

        def _provider(**kwargs):
            calls["count"] += 1
            pool = list(kwargs.get("pool", []) or [])
            return max(pool) if pool else None

        game = SimpleNamespace(
            map=SimpleNamespace(miracle_dice_provider=_provider),
            phase=SimpleNamespace(name="SHOOTING_PHASE"),
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
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

    def test_army_of_faith_sacred_rites_allows_two_acts_of_faith_per_phase(self):
        from warhammer40k_ai.rules import acts_of_faith as aof
        from warhammer40k_ai.rules.adepta_sororitas_detachments import AdeptaSororitasDetachmentManager

        calls = {"count": 0}

        def _provider(**kwargs):
            calls["count"] += 1
            pool = list(kwargs.get("pool", []) or [])
            return max(pool) if pool else None

        game = SimpleNamespace(
            map=SimpleNamespace(miracle_dice_provider=_provider),
            phase=SimpleNamespace(name="SHOOTING_PHASE"),
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = self._make_army("AS", player, detachment_type="Army of Faith")
        army.adepta_sororitas_detachments = AdeptaSororitasDetachmentManager(army)
        unit = self._make_unit("Sisters", army, acts=True)
        army.units.append(unit)

        mgr = aof.ActsOfFaithManager(army)
        mgr.miracle_dice = [6, 5, 4]

        old_get_dice_roll = aof.get_dice_roll
        aof.get_dice_roll = lambda _faces=6: 2
        try:
            roll_1, _dice_1, used_1 = mgr.resolve_roll(unit, roll_type="hit", game=game, dice_count=1, die_faces=6)
            roll_2, _dice_2, used_2 = mgr.resolve_roll(unit, roll_type="wound", game=game, dice_count=1, die_faces=6)
            roll_3, _dice_3, used_3 = mgr.resolve_roll(unit, roll_type="save", game=game, dice_count=1, die_faces=6)
        finally:
            aof.get_dice_roll = old_get_dice_roll

        self.assertTrue(used_1)
        self.assertTrue(used_2)
        self.assertFalse(used_3)
        self.assertEqual(roll_1, 6)
        self.assertEqual(roll_2, 5)
        self.assertEqual(roll_3, 2)
        self.assertEqual(mgr.miracle_dice, [4])
        self.assertEqual(calls["count"], 2)

    def test_litany_reroll_on_unit_destroyed(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
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

    def test_cherub_grants_one_bonus_miracle_die_after_act_of_faith_once_per_battle(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        def _provider(**kwargs):
            pool = list(kwargs.get("pool", []) or [])
            return max(pool) if pool else None

        game = SimpleNamespace(
            map=SimpleNamespace(miracle_dice_provider=_provider),
            phase=SimpleNamespace(name="SHOOTING_PHASE"),
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = self._make_army("AS", player)
        unit = self._make_unit("Sanctifiers", army, acts=True)
        unit.possible_abilities.append(
            SimpleNamespace(
                name="Cherub",
                description=(
                    "Once per battle, after this unit has performed an Act of Faith, you gain 1 Miracle dice. "
                    "Designer's Note: Place a Cherub token next to the unit, removing it once this ability has been used."
                ),
            )
        )
        army.units = [unit]

        mgr = aof.ActsOfFaithManager(army)
        mgr.miracle_dice = [6, 5]

        seq = iter([4, 3])
        old_get_roll = aof.get_roll
        old_get_dice_roll = aof.get_dice_roll
        aof.get_roll = lambda _s="D6": next(seq)
        aof.get_dice_roll = lambda _faces=6: 1
        try:
            roll_1, _dice_1, used_1 = mgr.resolve_roll(unit, roll_type="hit", game=game, dice_count=1, die_faces=6)
            game.phase.name = "CHARGE_PHASE"
            roll_2, _dice_2, used_2 = mgr.resolve_roll(unit, roll_type="charge", game=game, dice_count=2, die_faces=6)
        finally:
            aof.get_roll = old_get_roll
            aof.get_dice_roll = old_get_dice_roll

        self.assertTrue(used_1)
        self.assertTrue(used_2)
        self.assertEqual(roll_1, 6)
        self.assertEqual(roll_2, 6)
        self.assertEqual(mgr.miracle_dice, [4])
        self.assertEqual(int(unit.special_rules.get("acts_of_faith_cherub_uses", 0) or 0), 1)

    def test_cherubs_grants_two_bonus_miracle_dice_after_acts_of_faith(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        def _provider(**kwargs):
            pool = list(kwargs.get("pool", []) or [])
            return max(pool) if pool else None

        game = SimpleNamespace(
            map=SimpleNamespace(miracle_dice_provider=_provider),
            phase=SimpleNamespace(name="SHOOTING_PHASE"),
        )
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = self._make_army("AS", player)
        unit = self._make_unit("Retributors", army, acts=True)
        unit.possible_abilities.append(
            SimpleNamespace(
                name="Cherubs",
                description=(
                    "Twice per battle, after this unit has performed an Act of Faith, you gain 1 Miracle dice. "
                    "Designer's Note: Place two Cherub tokens next to the unit, removing one each time this ability has been used."
                ),
            )
        )
        army.units = [unit]

        mgr = aof.ActsOfFaithManager(army)
        mgr.miracle_dice = [6, 5, 4]

        seq = iter([1, 2, 3])
        old_get_roll = aof.get_roll
        old_get_dice_roll = aof.get_dice_roll
        aof.get_roll = lambda _s="D6": next(seq)
        aof.get_dice_roll = lambda _faces=6: 1
        try:
            roll_1, _dice_1, used_1 = mgr.resolve_roll(unit, roll_type="hit", game=game, dice_count=1, die_faces=6)
            game.phase.name = "CHARGE_PHASE"
            roll_2, _dice_2, used_2 = mgr.resolve_roll(unit, roll_type="charge", game=game, dice_count=2, die_faces=6)
            game.phase.name = "FIGHT_PHASE"
            roll_3, _dice_3, used_3 = mgr.resolve_roll(unit, roll_type="wound", game=game, dice_count=1, die_faces=6)
        finally:
            aof.get_roll = old_get_roll
            aof.get_dice_roll = old_get_dice_roll

        self.assertTrue(used_1)
        self.assertTrue(used_2)
        self.assertTrue(used_3)
        self.assertEqual(roll_1, 6)
        self.assertEqual(roll_2, 6)
        self.assertEqual(roll_3, 4)
        self.assertEqual(mgr.miracle_dice, [1, 2])
        self.assertEqual(int(unit.special_rules.get("acts_of_faith_cherub_uses", 0) or 0), 2)

    def test_saintly_example_grants_additional_d3_miracle_dice_once(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=SimpleNamespace(), phase=SimpleNamespace(name="FIGHT_PHASE"))
        player.game = game
        army = self._make_army("AS", player)
        enhancement = SimpleNamespace(name="Saintly Example", id="000008470002")
        unit = self._make_unit("Canoness", army, acts=True, enhancement=enhancement)
        army.units = [unit]
        mgr = aof.ActsOfFaithManager(army)

        seq = iter([2, 4, 5])  # D3 extra, then two D6 miracle dice.
        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": next(seq)
        try:
            mgr.on_model_destroyed(unit, unit.models[0], game=game)
            mgr.on_model_destroyed(unit, unit.models[0], game=game)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [4, 5])

    def test_recount_the_deeds_grants_miracle_die_when_led_unit_destroys_enemy_unit(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=SimpleNamespace(), phase=SimpleNamespace(name="SHOOTING_PHASE"))
        player.game = game
        enemy_player.game = game

        army = self._make_army("AS", player)
        enemy_army = self._make_army("ENEMY", enemy_player)

        bodyguard = self._make_unit("Battle Sisters", army, acts=True)
        leader = self._make_unit("Aestred Thurga And Agathae Dolan", army, acts=True)
        leader.possible_abilities.append(SimpleNamespace(name="Recount the Deeds of the Saints"))
        leader.models[0].name = "Agathae Dolan"
        leader.attached_to = bodyguard
        leader.get_attached_unit_root = lambda: bodyguard
        bodyguard.attached_leaders = [leader]
        army.units = [bodyguard, leader]

        enemy = self._make_unit("Enemy Squad", enemy_army, acts=False)
        enemy_army.units = [enemy]

        mgr = aof.ActsOfFaithManager(army)

        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": 6
        try:
            mgr.on_unit_destroyed(
                enemy,
                game=game,
                destroyed_by_unit=bodyguard,
                destroyed_by_model=bodyguard.models[0],
                destroyed_by_weapon_profile=None,
            )
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [6])

    def test_recount_the_deeds_requires_leading_and_agathae_alive_for_enemy_unit_kill_trigger(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        enemy_player = SimpleNamespace(name="P2", id="P2", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=SimpleNamespace(), phase=SimpleNamespace(name="FIGHT_PHASE"))
        player.game = game
        enemy_player.game = game

        army = self._make_army("AS", player)
        enemy_army = self._make_army("ENEMY", enemy_player)

        bodyguard = self._make_unit("Battle Sisters", army, acts=True)
        leader = self._make_unit("Aestred Thurga And Agathae Dolan", army, acts=True)
        leader.possible_abilities.append(SimpleNamespace(name="Recount the Deeds of the Saints"))
        leader.models[0].name = "Agathae Dolan"
        army.units = [bodyguard, leader]

        enemy = self._make_unit("Enemy Squad", enemy_army, acts=False)
        enemy_army.units = [enemy]

        mgr = aof.ActsOfFaithManager(army)

        # Not leading: no trigger.
        mgr.on_unit_destroyed(enemy, game=game, destroyed_by_unit=bodyguard)
        self.assertEqual(mgr.miracle_dice, [])

        # Leading but Agathae destroyed: no trigger.
        leader.attached_to = bodyguard
        leader.get_attached_unit_root = lambda: bodyguard
        bodyguard.attached_leaders = [leader]
        leader.models[0].wounds = 0
        mgr.on_unit_destroyed(enemy, game=game, destroyed_by_unit=bodyguard)
        self.assertEqual(mgr.miracle_dice, [])

    def test_recount_the_deeds_grants_d3_miracle_dice_when_agathae_is_destroyed_once(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(map=SimpleNamespace(), phase=SimpleNamespace(name="FIGHT_PHASE"))
        player.game = game
        army = self._make_army("AS", player)
        unit = self._make_unit("Aestred Thurga And Agathae Dolan", army, acts=True)
        unit.possible_abilities.append(SimpleNamespace(name="Recount the Deeds of the Saints"))
        unit.models[0].name = "Agathae Dolan"
        army.units = [unit]

        mgr = aof.ActsOfFaithManager(army)

        seq = iter([2, 4, 5])  # D3 extra, then two D6 miracle dice.
        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": next(seq)
        try:
            mgr.on_model_destroyed(unit, unit.models[0], game=game)
            mgr.on_model_destroyed(unit, unit.models[0], game=game)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [4, 5])

    def test_chaplet_of_sacrifice_rerolls_one_die_at_command_phase_end(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(
            map=SimpleNamespace(
                miracle_dice_pool_reroll_provider=lambda **_kwargs: {"indices": [0]},
            ),
            phase=SimpleNamespace(name="COMMAND_PHASE"),
        )
        game.get_current_player = lambda: player
        player.game = game
        army = self._make_army("AS", player)
        army.adepta_sororitas_detachments = SimpleNamespace(is_hallowed_martyrs=lambda: True)
        enhancement = SimpleNamespace(name="Chaplet of Sacrifice", id="000008470004")
        unit = self._make_unit("Palatine", army, acts=True, enhancement=enhancement)
        army.units = [unit]

        mgr = aof.ActsOfFaithManager(army)
        mgr.miracle_dice = [2, 5]

        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": 6
        try:
            mgr.on_command_phase_end(game=game, player=player)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [6, 5])

    def test_chaplet_of_sacrifice_rerolls_up_to_three_when_below_starting_strength(self):
        from warhammer40k_ai.rules import acts_of_faith as aof

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False)
        game = SimpleNamespace(
            map=SimpleNamespace(
                miracle_dice_pool_reroll_provider=lambda **_kwargs: {"indices": [0, 1, 2]},
            ),
            phase=SimpleNamespace(name="COMMAND_PHASE"),
        )
        game.get_current_player = lambda: player
        player.game = game
        army = self._make_army("AS", player)
        army.adepta_sororitas_detachments = SimpleNamespace(is_hallowed_martyrs=lambda: True)
        enhancement = SimpleNamespace(name="Chaplet of Sacrifice", id="000008470004")
        unit = self._make_unit("Canoness", army, acts=True, enhancement=enhancement)
        unit.is_below_starting_strength = lambda: True
        army.units = [unit]

        mgr = aof.ActsOfFaithManager(army)
        mgr.miracle_dice = [1, 2, 3, 6]

        seq = iter([4, 5, 6])
        old_get_roll = aof.get_roll
        aof.get_roll = lambda _s="D6": next(seq)
        try:
            mgr.on_command_phase_end(game=game, player=player)
        finally:
            aof.get_roll = old_get_roll

        self.assertEqual(mgr.miracle_dice, [4, 5, 6, 6])

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
            result = game.declare_charge(charger, [target])
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
