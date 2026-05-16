import unittest
from types import SimpleNamespace


class MockDatasheet:
    def __init__(self, name: str, *, ability_desc: str):
        self.name = name
        self.faction_data = {"name": "Aeldari"}
        self.keywords = ["VEHICLE"]
        self.faction_keywords = ["AELDARI"]
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 models", "cost": 100}]
        self.datasheets_models = [{
            "M": "10", "T": "8", "Sv": "3", "W": "12",
            "Ld": "7", "OC": "3",
            "base_size": "100mm", "inv_sv": "7", "inv_sv_descr": "none",
        }]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = [{
            "name": "Crystal Matrix",
            "description": ability_desc,
            "type": "Abilities",
            "parameter": None,
        }]
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, ability_desc: str):
    from warhammer40k_ai.units.unit import Unit
    return Unit(MockDatasheet(name, ability_desc=ability_desc))


class TestSelectedToShootRerolls(unittest.TestCase):
    def test_selected_to_shoot_rerolls_once(self):
        from warhammer40k_ai.units.wargear import WargearProfile
        from warhammer40k_ai.utility.model_base import Base, BaseType

        ability_text = (
            "Each time this model is selected to shoot, you can re-roll one Hit roll and you can re-roll one Wound roll "
            "when resolving those attacks."
        )
        attacker_unit = make_unit("Fire Prism", ability_desc=ability_text)
        target_unit = make_unit("Target", ability_desc="")

        attacker_model = attacker_unit.models[0]
        attacker_model.parent_unit = attacker_unit
        target_model = target_unit.models[0]
        target_model.parent_unit = target_unit

        # Ensure model bases exist for any distance calculations
        attacker_model.model_base = Base(BaseType.CIRCULAR, 1.0)
        target_model.model_base = Base(BaseType.CIRCULAR, 1.0)

        attacker_unit.grant_selected_to_shoot_rerolls_for_models([attacker_model])

        ranged_parent = SimpleNamespace(
            name="Test Gun",
            is_melee=lambda: False,
            is_ranged=lambda: True,
        )
        prof = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "8",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

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
            2, 5,  # hit roll fail, then reroll success
            2, 5,  # wound roll fail, then reroll success
            2,     # second hit roll fail, no reroll remaining
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            attack_instance = {"_aura_attack_mods": aura_stub}
            hit_res = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(hit_res.get("hit"))
            self.assertEqual(hit_res.get("reroll"), 5)
            self.assertTrue(any("Crystal Matrix" in x for x in hit_res.get("special_effects", [])))
            self.assertFalse(attacker_model.can_use_selected_to_shoot_reroll("hit"))

            wound_res = prof._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(wound_res.get("wound"))
            self.assertEqual(wound_res.get("reroll"), 5)
            self.assertTrue(any("Crystal Matrix" in x for x in wound_res.get("special_effects", [])))
            self.assertFalse(attacker_model.can_use_selected_to_shoot_reroll("wound"))

            hit_res2 = prof._hit_target_with_tracking(target_unit, attacker_model, attack_instance, roll_value=2)
            self.assertIsNone(hit_res2.get("reroll"))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
