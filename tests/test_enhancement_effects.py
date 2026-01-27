import unittest
from types import SimpleNamespace


class TestEnhancementEffects(unittest.TestCase):
    def test_classify_requires_full_consumption_for_conditionals(self):
        from warhammer40k_ai.rules.enhancement_effects import classify_enhancement_support

        status, notes = classify_enhancement_support(
            "ADEPTA SORORITAS model only. Add 1 to the Attacks, Strength and Damage characteristics of the bearer's melee weapons. "
            "If the bearer has lost one or more wounds, add 2 to the Attacks, Strength and Damage characteristics of the bearer's melee weapons instead."
        )

        self.assertEqual(status, "Partial")
        self.assertIn("Improve melee weapons' A/S/D by 1", notes)

    def test_classify_supported_when_fully_consumed(self):
        from warhammer40k_ai.rules.enhancement_effects import classify_enhancement_support

        status, notes = classify_enhancement_support(
            "Add 1 to the Attacks, Strength and Damage characteristics of the bearer's melee weapons."
        )

        self.assertEqual(status, "Supported")
        self.assertIn("Improve melee weapons' A/S/D by 1", notes)

    def test_move_add_uses_modifier_pipeline(self):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.rules.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects
        from warhammer40k_ai.utility.modifiers import apply_numeric_modifiers, apply_characteristic_caps

        class UnitStub:
            def __init__(self):
                self.special_rules = {}
                self.models = []
                self._characteristic_modifiers = {}

            def add_characteristic_modifier(self, characteristic: str, modifier) -> None:
                key = str(characteristic).strip().lower()
                self._characteristic_modifiers.setdefault(key, []).append(modifier)

            def get_effective_model_characteristic(self, model, characteristic: str, *, game_map=None) -> int:
                c = str(characteristic).strip().lower()
                if c != "movement":
                    raise AssertionError("UnitStub only supports movement for this test")
                base = int(getattr(model, "_movement", 0))
                mods = list(self._characteristic_modifiers.get("movement", []) or [])
                out, _dbg = apply_numeric_modifiers(base, mods, base_raw=getattr(model, "_movement_raw", None))
                out = apply_characteristic_caps("movement", out, base_raw=getattr(model, "_movement_raw", None))
                return int(out)

        unit = UnitStub()
        m = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(unit)
        unit.models = [m]

        effects = parse_enhancement_effects('Add 2" to the bearer\'s Move characteristic.')
        apply_enhancement_effects(unit, effects)

        self.assertIn("movement", unit._characteristic_modifiers)
        self.assertEqual(len(unit._characteristic_modifiers["movement"]), 1)
        self.assertEqual(m.movement, 8)

    def test_wounds_add_increases_base_and_current(self):
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.rules.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        unit = SimpleNamespace(stats={}, special_rules={}, models=[], starting_total_wounds=0)
        m = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=5,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        m.set_parent_unit(unit)
        unit.models = [m]
        unit.starting_total_wounds = m._base_wounds

        effects = parse_enhancement_effects("Add 2 to the bearer's Wounds characteristic.")
        apply_enhancement_effects(unit, effects)

        self.assertEqual(m._base_wounds, 7)
        self.assertEqual(m.wounds, 7)
        self.assertEqual(unit.starting_total_wounds, 7)

    def test_melee_asd_bonus_affects_wound_roll_strength(self):
        # S4 vs T5 normally wounds on 5+. With +1S enhancement, wounds on 4+.
        from unittest.mock import patch

        from warhammer40k_ai.units.wargear import Wargear, WargearProfile
        from warhammer40k_ai.rules.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        attacker_unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        target_unit = SimpleNamespace(toughness=5, models=[SimpleNamespace(is_alive=True)])

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        profile: WargearProfile = parent.profiles["default"]

        # No enhancement: roll 4 should fail (needs 5+)
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance={})
        self.assertFalse(res["wound"])

        # Apply enhancement: +1S
        effects = parse_enhancement_effects(
            "Improve the Attacks, Strength and Damage characteristics of melee weapons equipped by the bearer by 1."
        )
        apply_enhancement_effects(attacker_unit, effects)

        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=4):
            res2 = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance={})
        self.assertTrue(res2["wound"])

    def test_reduce_damage_taken_applies_min_1(self):
        from warhammer40k_ai.units.wargear import Wargear, WargearProfile
        from warhammer40k_ai.units.model import Model
        from warhammer40k_ai.utility.model_base import Base, BaseType
        from warhammer40k_ai.rules.enhancement_effects import apply_enhancement_effects, parse_enhancement_effects

        attacker_unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        attacker_model = SimpleNamespace(name="Attacker", parent_unit=attacker_unit)

        target_unit = SimpleNamespace(
            stats={},
            special_rules={},
            models=[],
            has_feel_no_pain=lambda: [],
            damaged_profile=None,
            damaged_profile_desc=None,
        )
        target_model = Model(
            name="Bearer",
            movement=6,
            toughness=4,
            save=3,
            wounds=10,
            leadership=6,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        target_model.set_parent_unit(target_unit)
        target_unit.models = [target_model]

        apply_enhancement_effects(
            target_unit,
            parse_enhancement_effects("Each time an attack is allocated to the bearer, subtract 1 from the Damage characteristic of that attack."),
        )

        data = {
            "range": "Melee",
            "A": "1",
            "BS_WS": "3",
            "S": "4",
            "AP": "0",
            "D": "1",
            "description": "",
            "type": "Melee",
            "name": "Test Weapon",
        }
        parent = Wargear(data)
        profile: WargearProfile = parent.profiles["default"]

        attack_instance = {"below_half_distance": False, "mortal_wound": False}
        before = target_model.wounds
        profile._damage_target_with_tracking(target_model, attacker_model, attack_instance, game_map=None)
        # Damage is 1, reduced by 1 but min 1 => still 1
        self.assertEqual(target_model.wounds, before - 1)

    def test_reroll_advance_charge_enhancement_sets_flags(self):
        from warhammer40k_ai.rules.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        effects = parse_enhancement_effects(
            "Ravenwing model only. You can re-roll Advance and Charge rolls made for the bearer's unit."
        )
        apply_enhancement_effects(unit, effects)

        self.assertTrue(unit.special_rules.get("enhancement_reroll_advance"))
        self.assertTrue(unit.special_rules.get("enhancement_charge_reroll"))

    def test_reroll_charge_objective_enhancement_sets_flag(self):
        from warhammer40k_ai.rules.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        effects = parse_enhancement_effects(
            "Adeptus Astartes model only. Each time the bearer's unit declares a charge, if one or more targets of that charge are within range of an objective marker, you can re-roll the Charge roll."
        )
        apply_enhancement_effects(unit, effects)

        self.assertTrue(unit.special_rules.get("enhancement_charge_reroll_if_target_on_objective"))

    def test_reroll_charge_setup_turn_enhancement_sets_flag(self):
        from warhammer40k_ai.rules.enhancement_effects import parse_enhancement_effects, apply_enhancement_effects

        unit = SimpleNamespace(stats={}, special_rules={}, models=[])
        effects = parse_enhancement_effects(
            "Adeptus Astartes model only. You can re-roll Charge rolls made for the bearer's unit in a turn in which it was set up on the battlefield."
        )
        apply_enhancement_effects(unit, effects)

        self.assertTrue(unit.special_rules.get("enhancement_charge_reroll_on_setup_turn"))


if __name__ == "__main__":
    unittest.main()
