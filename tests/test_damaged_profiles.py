import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _DummyTargetUnit:
    def __init__(self):
        self.name = "Target"
        self.models = [SimpleNamespace(is_alive=True)]

    def has_stealth(self):
        return False


class TestDamagedProfiles(unittest.TestCase):
    def test_damaged_profile_applies_minus_one_to_hit(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.utility.range import Range

        # Build a unit+model with a damaged profile
        u = Unit.__new__(Unit)
        u.name = "Venerable Land Raider"
        u.stats = {}
        u.special_rules = {}
        u._damaged_profile_stat_deltas = {}
        u._damaged_profile_active = False
        u.damaged_profile = Range.from_string("1-5")
        u.damaged_profile_desc = "While this model has 1-5 wounds remaining, each time this model makes an attack, subtract 1 from the Hit roll."

        m = Model(
            name="Model",
            movement=6,
            toughness=10,
            save=2,
            wounds=4,
            leadership=6,
            objective_control=5,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(u)
        u.models = [m]

        # Trigger damaged profile
        m._check_damaged_profile()
        self.assertEqual(u.special_rules.get("damaged_hit_roll_modifier"), -1)

        # Weapon with WS/BS 3+; roll 3 would normally hit, but with -1 to hit becomes 4+ and fails.
        w = Wargear({"name": "Test gun", "type": "Ranged", "range": "24", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1", "description": ""})
        prof = w.profiles["default"]
        target = _DummyTargetUnit()

        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=3):
            res = prof._hit_target_with_tracking(target, m, attack_instance={})
        self.assertFalse(res["hit"])

        # Heal above threshold -> effects cleared -> roll 3 hits again
        m.wounds = 6
        m._check_damaged_profile()
        self.assertNotIn("damaged_hit_roll_modifier", u.special_rules)
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=3):
            res2 = prof._hit_target_with_tracking(target, m, attack_instance={})
        self.assertTrue(res2["hit"])

    def test_damaged_profile_applies_objective_control_penalty(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.utility.range import Range

        u = Unit.__new__(Unit)
        u.name = "Wraithknight"
        u.stats = {}
        u.special_rules = {}
        u._damaged_profile_stat_deltas = {}
        u._damaged_profile_active = False
        u.damaged_profile = Range.from_string("1-6")
        u.damaged_profile_desc = "While this model has 1-6 wounds remaining, subtract 5 from this model's Objective Control characteristic and each time this model makes an attack, subtract 1 from the Hit roll."

        m = Model(
            name="Model",
            movement=12,
            toughness=12,
            save=2,
            wounds=6,
            leadership=6,
            objective_control=10,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(u)
        u.models = [m]

        m._check_damaged_profile()
        self.assertEqual(m.objective_control, 5)

        # Clear
        m.wounds = 7
        m._check_damaged_profile()
        self.assertEqual(m.objective_control, 10)

    def test_damaged_profile_halves_attacks_rounding_up(self):
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.utility.range import Range

        u = Unit.__new__(Unit)
        u.name = "The Silent King"
        u.stats = {}
        u.special_rules = {}
        u._damaged_profile_stat_deltas = {}
        u._damaged_profile_active = False
        u.damaged_profile = Range.from_string("1-6")
        u.damaged_profile_desc = "While this unit's Szarekh model has 1-6 wounds remaining, halve the Attacks characteristic of that model's weapons, and each time this unit makes an attack, subtract 1 from the Hit roll."

        m = Model(
            name="Szarekh",
            movement=8,
            toughness=8,
            save=2,
            wounds=6,
            leadership=6,
            objective_control=3,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(u)
        u.models = [m]

        m._check_damaged_profile()
        self.assertTrue(u.special_rules.get("damaged_half_attacks", False))

        # Use a weapon with 3 attacks; halved should be 2 (round up).
        w = Wargear({"name": "Test melee", "type": "Melee", "range": "Melee", "A": "3", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1", "description": ""})
        prof = w.profiles["default"]

        # We don't want to run full attack resolution; just patch out internals by forcing early exit:
        # set ONE SHOT false and provide minimal target.
        target = _DummyTargetUnit()
        # Patch closest-model distance and hit/wound/save to avoid deep dependencies; just verify attack loop count indirectly.
        # Here we inspect the computed num_attacks by patching Count.resolve_detailed for attacks is not used (flat int),
        # so easiest is to patch range check and then patch get_roll to always hit and wound but not crash.
        with patch.object(
            prof,
            "_hit_target_with_tracking",
            return_value={"hit": False, "roll": 1, "needed": 3, "final_needed": 3, "modifiers": [], "special_effects": []},
        ) as hit_mock:
            # If halving didn't happen we'd attempt 3 hit calls; with halving we attempt 2.
            with patch.object(m, "return_closest_model_in_unit", return_value=(m, 1.0)):
                with patch.object(prof, "_print_attack_summary", return_value=None):
                    prof.attack(target, m, game_map=None)
        self.assertEqual(hit_mock.call_count, 2)

    def test_damaged_profile_adds_melee_attacks(self):
        # Skarbrand style: add +2 to attacks of melee weapons while damaged.
        from warhammer40k_ai.classes.unit import Unit
        from warhammer40k_ai.classes.model import Model
        from warhammer40k_ai.classes.wargear import Wargear
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.utility.range import Range

        u = Unit.__new__(Unit)
        u.name = "Skarbrand"
        u.stats = {}
        u.special_rules = {}
        u._damaged_profile_stat_deltas = {}
        u._damaged_profile_active = False
        u.damaged_profile = Range.from_string("1-7")
        u.damaged_profile_desc = "While this model has 1-7 wounds remaining, add 2 to the Attacks characteristic of this model's melee weapons."

        m = Model(
            name="Model",
            movement=8,
            toughness=10,
            save=2,
            wounds=7,
            leadership=6,
            objective_control=3,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(u)
        u.models = [m]
        m._check_damaged_profile()

        w = Wargear({"name": "Test melee", "type": "Melee", "range": "Melee", "A": "1", "BS_WS": "3+", "S": "4", "AP": "0", "D": "1", "description": ""})
        prof = w.profiles["default"]
        target = _DummyTargetUnit()

        with patch.object(prof, "_hit_target_with_tracking", return_value={"hit": False, "roll": 1, "needed": 3, "final_needed": 3, "modifiers": [], "special_effects": []}) as hit_mock:
            with patch.object(m, "return_closest_model_in_unit", return_value=(m, 1.0)):
                with patch.object(prof, "_print_attack_summary", return_value=None):
                    prof.attack(target, m, game_map=None)

        # Base 1 attack +2 => 3 attacks -> 3 hit calls
        self.assertEqual(hit_mock.call_count, 3)


if __name__ == "__main__":
    unittest.main()

