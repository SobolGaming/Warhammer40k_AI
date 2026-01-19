import unittest
from types import SimpleNamespace


class TestOathOfMoment(unittest.TestCase):
    def test_oath_command_phase_clears_and_selects_target(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))
                self._army = None
                self.embarked_in = None

            def set_army(self, army):
                self._army = army

            def get_parent_army(self):
                return self._army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

        enemy_unit = _Unit("Enemy1")
        old_unit = _Unit("OldTarget")

        player = SimpleNamespace(
            name="P1",
            id="P1",
            control=SimpleNamespace(name="REMOTE"), has_control=lambda: False,
            _choose_optional_value=lambda *_a, **_k: None,
        )
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        player.get_army = lambda: army
        army.player = player

        for u in (enemy_unit, old_unit):
            u.set_army(army)

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr

        # Pre-seed a stale target that should be cleared/replaced.
        mgr.set_target(old_unit)
        self.assertEqual(mgr.oathOfMomentTargetUnitId, old_unit._id)

        class _Game:
            def get_enemy_units(self, _player):
                return [enemy_unit]

        mgr.on_command_phase_start(game=_Game(), player=player)
        self.assertEqual(mgr.oathOfMomentTargetUnitId, enemy_unit._id)

    def test_oath_reroll_hit_and_wound_bonus(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        # Minimal game/player/army wiring for roll_made publish calls
        game = SimpleNamespace(event_system=EventSystem(), map=None)
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        army.player = player

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str, keywords=None):
                self.name = name
                self._id = name
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}
                self._keywords = set((keywords or []))
                self.embarked_in = None

            def get_parent_army(self):
                return army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def has_any_keyword(self, keyword: str) -> bool:
                return keyword.strip().upper() in {k.upper() for k in self._keywords}

            def get_models_for_wound_allocation(self):
                return self.models

        attacker_unit = _Unit("Intercessors", keywords=["ADEPTUS ASTARTES"])
        target_unit = _Unit("Target")
        army.units = [attacker_unit]

        mgr = OathOfMomentManager(army)
        army.oath_of_moment = mgr
        mgr.set_target(target_unit)

        attacker_model = Model(
            name="Marine",
            movement=6,
            toughness=4,
            save=3,
            wounds=2,
            leadership=6,
            objective_control=2,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        attacker_model.parent_unit = attacker_unit

        target_model = Model(
            name="Enemy",
            movement=6,
            toughness=5,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.parent_unit = target_unit
        target_unit.models = [target_model]

        melee_parent = SimpleNamespace(name="Test Weapon", is_melee=lambda: True)
        prof = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
        )

        # Provide aura mods to avoid importing aura system
        aura_stub = SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

        from warhammer40k_ai.units import wargear as wargear_mod
        seq = iter([
            2, 5,  # hit roll fail then reroll success (4+)
            4,     # wound roll (S==T => 4+; +1 from Oath makes it 3+)
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["roll"]), 5)
            self.assertTrue(any("Oath of Moment" in x for x in hit_res.get("special_effects", [])))

            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Oath of Moment" in x for x in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_oath_excludes_embarked_targets(self):
        from warhammer40k_ai.roster.army import Army
        from warhammer40k_ai.rules.oath_of_moment import OathOfMomentManager

        class _Unit:
            def __init__(self, name: str):
                self.name = name
                self._id = name
                self.embarked_in = None

            def get_attached_unit_root(self):
                return self

            @property
            def is_embarked(self):
                return self.embarked_in is not None

            def is_alive(self):
                return True

        embarked = _Unit("EmbarkedUnit")
        embarked.embarked_in = object()
        available = _Unit("AvailableUnit")

        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="REMOTE"), has_control=lambda: False, _choose_optional_value=lambda *_a, **_k: None)
        army = Army("Space Marines", "Gladius Task Force")
        army.faction_id = "SM"
        player.get_army = lambda: army
        army.player = player

        mgr = OathOfMomentManager(army)

        class _Game:
            def get_enemy_units(self, _player):
                return [embarked, available]

        mgr.on_command_phase_start(game=_Game(), player=player)
        self.assertEqual(mgr.oathOfMomentTargetUnitId, available._id)


if __name__ == "__main__":
    unittest.main()
