import unittest
from types import SimpleNamespace

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


class TestProtectPsychicWoundPenalty(unittest.TestCase):
    def _make_unit(self, name, *, keywords=None, faction_keywords=None, abilities=None):
        unit = Unit.__new__(Unit)
        unit.name = name
        unit._id = name
        unit.parent_army = None
        unit.faction = ""
        unit.deployed = True
        unit.reserve_status = "deployed"
        unit.models = []
        unit.models_lost = []
        unit.keywords = list(keywords or [])
        unit.faction_keywords = list(faction_keywords or [])
        unit.possible_abilities = list(abilities or [])
        unit.status_effects = []
        unit.special_rules = {}
        unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
        unit.attached_leaders = []
        unit.attached_to = None
        unit.can_be_attached_to = []
        unit.embarked_in = None
        unit._ability_cache = {}
        unit.is_alive = lambda: True
        unit.get_parent_army = lambda: unit.parent_army
        unit.get_attached_unit_root = lambda: unit
        unit.get_attached_unit_models = lambda: list(unit.models)
        unit.get_attached_unit_members = lambda: [unit]
        unit.is_in_reserves = lambda: False
        unit.has_any_keyword = lambda kw: any(
            str(kw or "").strip().upper() == str(k or "").strip().upper()
            for k in (unit.keywords + unit.faction_keywords)
        )
        return unit

    def _make_model(self, name, unit, toughness=4):
        model = Model(
            name=name,
            movement=6,
            toughness=toughness,
            save=3,
            wounds=2,
            leadership=7,
            objective_control=1,
            model_base=Base(BaseType.CIRCULAR, 1.0),
        )
        model.parent_unit = unit
        model.set_location(0.0, 0.0, 0.0, 0.0)
        return model

    def test_protect_psychic_applies_wound_penalty(self):
        ability_desc = (
            "While a Farseer model is leading this unit, each time an attack targets this unit, "
            "subtract 1 from the Wound roll."
        )
        ability = Ability("Protect (Psychic)", "AE", ability_desc, "Datasheet", "")

        target_unit = self._make_unit("Guardians", keywords=["Infantry"], abilities=[ability])
        target_model = self._make_model("Guardian", target_unit, toughness=4)
        target_unit.models = [target_model]

        leader = self._make_unit("Farseer", keywords=["Farseer", "Character"])
        leader_model = self._make_model("Farseer", leader)
        leader.models = [leader_model]
        target_unit.attached_leaders = [leader]

        target_unit._parse_against_attack_characteristic_defensive_rules()

        attacker_unit = self._make_unit("Attacker")
        attacker_model = self._make_model("Attacker", attacker_unit, toughness=4)
        attacker_unit.models = [attacker_model]

        ranged_parent = SimpleNamespace(name="Ranged Weapon", is_melee=lambda: False)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "4+",
                "S": "5",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        from warhammer40k_ai.units import wargear as wargear_mod
        old_get_roll = wargear_mod.get_roll
        wargear_mod.get_roll = lambda _s: 4
        try:
            wound_res = profile._wound_target_with_tracking(target_unit, attacker_model, {}, allow_rerolls=False)
            self.assertTrue(any("Protect" in mod for mod in wound_res.get("modifiers", [])))
        finally:
            wargear_mod.get_roll = old_get_roll


if __name__ == "__main__":
    unittest.main()
