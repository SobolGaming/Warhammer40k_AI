import unittest
from types import SimpleNamespace
from unittest.mock import patch


class TestMortalWoundsOrdering(unittest.TestCase):
    def test_normal_damage_resolved_before_mortal_wounds(self):
        """
        Rule: if an attack sequence inflicts a mixture of mortal wounds and normal damage,
        resolve all normal damage first. Saving throws cannot be made against mortal wounds.
        """
        from warhammer40k_ai.units.wargear import Wargear

        # 2 attacks; Devastating Wounds => critical wound produces mortal wounds.
        w = Wargear(
            {
                "name": "Test Weapon",
                "type": "Ranged",
                "range": "24",
                "A": "2",
                "BS_WS": "2+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "Devastating Wounds",
            }
        )
        prof = w.profiles["default"]

        # Minimal attacker/target stubs
        attacker_unit = SimpleNamespace(round_state=SimpleNamespace(remained_stationary_this_round=False), special_rules={})
        attacker = SimpleNamespace(
            name="A",
            parent_unit=attacker_unit,
            has_temporary_devastating_wounds_melee=lambda: False,
            # Used for below-half-range calculations in WargearProfile.attack()
            return_closest_model_in_unit=lambda _unit: (None, 0.0),
        )

        target_model = SimpleNamespace(name="T", save=3, inv_save=(None, ""), parent_unit=None)
        target_unit = SimpleNamespace(
            name="Target",
            toughness=4,
            has_keyword=lambda _k: False,
            has_stealth=lambda: False,
            get_models_for_wound_allocation=lambda: [target_model],
            has_feel_no_pain=lambda: [],
        )
        target_model.parent_unit = target_unit

        # Track ordering of damage applications and save calls.
        damage_order = []
        save_calls = {"n": 0}

        def _damage_stub(_target_model, _attacker, attack_instance, game_map=None):
            damage_order.append(bool(attack_instance.get("mortal_wound", False)))
            return {
                "damage_rolled": 1,
                "damage_applied": 1,
                "target_model": getattr(_target_model, "name", "T"),
                "excess_damage": 0,
                "model_killed": False,
                "fnp_saves": 0,
                "fnp_rolls": [],
                "damage_dice_rolls": [],
                "damage_expression": "1",
                "special_effects": [],
            }

        def _save_stub(_target_model, _attack_instance, _ap):
            save_calls["n"] += 1
            return {"saved": False, "roll": 2, "needed": 3, "save_type": "armor", "base_save": 3, "ap_modifier": 0, "final_save": 3, "special_effects": []}

        prof._damage_target_with_tracking = _damage_stub
        prof._save_with_tracking = _save_stub

        # Hit rolls: 6, 6 (both hits)
        # Wound rolls: 6 (crit -> mortal), 4 (normal wound)
        # Save roll: handled by _save_stub; no get_roll needed for save.
        with patch("warhammer40k_ai.units.wargear.get_roll", side_effect=[6, 6, 6, 4]):
            prof.attack(target_unit, attacker, game_map=None)

        # Only the normal wound should roll a save.
        self.assertEqual(save_calls["n"], 1)
        # Damage should be resolved normal first (False), then mortal (True), even if mortal wound was generated first.
        self.assertEqual(damage_order, [False, True])


if __name__ == "__main__":
    unittest.main()


