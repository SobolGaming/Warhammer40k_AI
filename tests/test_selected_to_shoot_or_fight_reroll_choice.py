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
            "name": "Test Ability",
            "description": ability_desc,
            "type": "Abilities",
            "parameter": None,
        }]
        self.loadout = "This model is equipped with: nothing"


def make_unit(name: str, *, ability_desc: str):
    from warhammer40k_ai.units.unit import Unit
    return Unit(MockDatasheet(name, ability_desc=ability_desc))


class TestSelectedToShootOrFightRerollChoice(unittest.TestCase):
    def _build_profile(self, *, ranged: bool):
        from warhammer40k_ai.units.wargear import WargearProfile

        parent = SimpleNamespace(
            name="Test Weapon",
            is_melee=(lambda: not ranged),
            is_ranged=(lambda: ranged),
        )
        profile = WargearProfile(
            profile_name="Ranged" if ranged else "Melee",
            wargear_data={
                "range": "24" if ranged else "Melee",
                "A": "1",
                "BS_WS": "4+",
                "S": "8",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        return profile

    def _aura_stub(self):
        return SimpleNamespace(
            hit=0,
            wound=0,
            reroll_hit_ones=False,
            reroll_wound_ones=False,
            reroll_hit_reasons=(),
            reroll_wound_reasons=(),
            target_toughness_delta=0,
            target_toughness_reasons=(),
        )

    def _setup_models(self, ability_text: str):
        from warhammer40k_ai.utility.model_base import Base, BaseType

        attacker_unit = make_unit("Attacker", ability_desc=ability_text)
        target_unit = make_unit("Target", ability_desc="")

        attacker_model = attacker_unit.models[0]
        attacker_model.parent_unit = attacker_unit
        target_model = target_unit.models[0]
        target_model.parent_unit = target_unit

        attacker_model.model_base = Base(BaseType.CIRCULAR, 1.0)
        target_model.model_base = Base(BaseType.CIRCULAR, 1.0)

        return attacker_unit, attacker_model, target_unit

    def test_selected_to_shoot_or_fight_reroll_choice_hit_used(self):
        ability_text = (
            "Each time this model is selected to shoot or fight, you can re-roll one Hit roll "
            "or you can re-roll one Wound roll when resolving those attacks."
        )
        attacker_unit, attacker_model, target_unit = self._setup_models(ability_text)
        attacker_unit.grant_selected_to_action_reroll_choice_for_models([attacker_model], action="shoot")

        profile = self._build_profile(ranged=True)
        attack_instance = {"_aura_attack_mods": self._aura_stub()}

        from warhammer40k_ai.units import wargear as wargear_mod

        seq = iter([
            2, 5,  # hit roll fail, then reroll success
            2,     # wound roll fail, no reroll remaining
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Test Ability" in x for x in hit_res.get("special_effects", [])))
            self.assertFalse(attacker_model.can_use_selected_to_action_reroll("hit", "shoot"))

            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertIsNone(wound_res.get("reroll"))
            self.assertFalse(attacker_model.can_use_selected_to_action_reroll("wound", "shoot"))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_selected_to_shoot_or_fight_reroll_choice_wound_used(self):
        ability_text = (
            "Each time this model is selected to shoot or fight, you can re-roll one Hit roll "
            "or you can re-roll one Wound roll when resolving those attacks."
        )
        attacker_unit, attacker_model, target_unit = self._setup_models(ability_text)
        attacker_unit.grant_selected_to_action_reroll_choice_for_models([attacker_model], action="shoot")

        profile = self._build_profile(ranged=True)
        attack_instance = {"_aura_attack_mods": self._aura_stub()}

        from warhammer40k_ai.units import wargear as wargear_mod

        seq = iter([
            5,     # hit roll success, no reroll used
            2, 5,  # wound roll fail, then reroll success
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertIsNone(hit_res.get("reroll"))

            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Test Ability" in x for x in wound_res.get("special_effects", [])))
            self.assertFalse(attacker_model.can_use_selected_to_action_reroll("wound", "shoot"))
        finally:
            wargear_mod.get_roll = old_get_roll

    def test_selected_to_shoot_or_fight_reroll_choice_fight_hit(self):
        ability_text = (
            "Each time this model is selected to shoot or fight, you can re-roll one Hit roll "
            "or you can re-roll one Wound roll when resolving those attacks."
        )
        attacker_unit, attacker_model, target_unit = self._setup_models(ability_text)
        attacker_unit.grant_selected_to_action_reroll_choice_for_models([attacker_model], action="fight")

        profile = self._build_profile(ranged=False)
        attack_instance = {"_aura_attack_mods": self._aura_stub()}

        from warhammer40k_ai.units import wargear as wargear_mod

        seq = iter([
            2, 5,  # hit roll fail, then reroll success
        ])
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: next(seq)
        try:
            hit_res = profile._hit_target_with_tracking(target_unit, attacker_model, attack_instance)
            self.assertTrue(any("Test Ability" in x for x in hit_res.get("special_effects", [])))
            self.assertFalse(attacker_model.can_use_selected_to_action_reroll("hit", "fight"))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
