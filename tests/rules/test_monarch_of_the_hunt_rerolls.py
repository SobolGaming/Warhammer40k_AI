import unittest
from types import SimpleNamespace

from warhammer40k_ai.engine.decision_port import DecisionPort


class TestMonarchOfTheHuntRerolls(unittest.TestCase):
    def test_melee_hit_and_wound_are_rerolled_vs_quarry(self):
        from warhammer40k_ai.engine.event.system import EventSystem
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.units.wargear import WargearProfile

        # Minimal game/player/army wiring for roll_made publish calls
        game = SimpleNamespace(
            event_system=EventSystem(),
            map=SimpleNamespace(),
            decision_port=DecisionPort({"roll_reroll_provider": lambda **k: not k.get("success")}),
        )
        game.map.game = game
        player = SimpleNamespace(name="P1", id="P1", control=SimpleNamespace(name="LOCAL"), has_control=lambda: True, game=game)
        army = SimpleNamespace(player=player)

        class _Round:
            remained_stationary_this_round = False
            charged_this_round = False

        class _Unit:
            def __init__(self, name: str):
                self.name = name
                self._id = name  # stable for test
                self.toughness = 5
                self.round_state = _Round()
                self.models = []
                self.special_rules = {}

            def get_parent_army(self):
                return army

            def get_attached_unit_root(self):
                return self

            def is_alive(self):
                return True

        attacker_unit = _Unit("Shalaxi")
        target_unit = _Unit("QuarryUnit")

        # Set quarry IDs on attacker unit
        attacker_unit._monarch_of_the_hunt_quarry_ids = {target_unit._id}

        attacker_model = Model(
            name="Shalaxi",
            movement=6,
            toughness=10,
            save=3,
            wounds=12,
            leadership=6,
            objective_control=4,
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

        melee_parent = SimpleNamespace(name="Test Melee Weapon", is_melee=lambda: True)
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
            2, 6,  # wound roll fail then reroll success (S==T => 4+)
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(hit_res["roll"]), 5)
            self.assertTrue(any("Monarch of the Hunt" in x for x in hit_res.get("special_effects", [])))

            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertEqual(int(wound_res["roll"]), 6)
            self.assertTrue(any("Monarch of the Hunt" in x for x in wound_res.get("special_effects", [])))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
