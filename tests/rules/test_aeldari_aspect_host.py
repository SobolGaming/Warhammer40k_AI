import unittest
from types import SimpleNamespace

from warhammer40k_ai.roster.army import Army
from warhammer40k_ai.rules.enhancement import Enhancement
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import WargearProfile
from warhammer40k_ai.utility.model_base import Base, BaseType


def _make_unit(name, army, *, keywords=None, faction_keywords=None):
    unit = Unit.__new__(Unit)
    unit.name = name
    unit._id = name
    unit.parent_army = army
    unit.faction = getattr(army, "faction_id", "")
    unit.deployed = True
    unit.reserve_status = "deployed"
    unit.models = []
    unit.models_lost = []
    unit.keywords = list(keywords or [])
    unit.faction_keywords = list(faction_keywords or [])
    unit.possible_abilities = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.round_state = SimpleNamespace(num_lost_models_this_round=0)
    unit.attached_leaders = []
    unit.attached_to = None
    unit.can_be_attached_to = []
    unit.embarked_in = None
    unit._ability_cache = {}
    unit.enhancement = None
    unit.is_alive = lambda: True
    unit.get_parent_army = lambda: army
    unit.get_attached_unit_root = lambda: unit
    unit.get_attached_unit_models = lambda: list(unit.models)
    unit.get_attached_unit_members = lambda: [unit]
    unit.get_models_for_collision = lambda: list(unit.models)
    unit.is_in_reserves = lambda: False
    unit.has_any_keyword = lambda kw: any(
        str(kw or "").strip().upper() == str(k or "").strip().upper()
        for k in (unit.keywords + unit.faction_keywords)
    )
    return unit


def _make_model(name, unit, *, x=0.0, y=0.0, wounds=6):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=wounds,
        leadership=7,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


class TestAeldariAspectHost(unittest.TestCase):
    def test_aspect_of_murder_precision_and_damage(self):
        army = Army.with_detachment("Aeldari", detachment_type="Aspect Host")
        army.faction_id = "AE"

        enhancer = Enhancement(
            id="000009927002",
            name="Aspect of Murder",
            faction_id="AE",
            detachment="Aspect Host",
            description=(
                "Autarch or Autarch Wayleaper model only. "
                "Add 1 to the Damage characteristic of melee weapons equipped by the bearer, "
                "and those weapons have the [precision] ability."
            ),
        )

        unit = _make_unit("Autarch", army, faction_keywords=["AELDARI", "CHARACTER"])
        model = _make_model("Autarch", unit, x=0.0, y=0.0, wounds=5)
        unit.models = [model]
        unit.enhancement = enhancer
        enhancer.apply_to_unit(unit)

        sr = unit.special_rules or {}
        self.assertEqual(sr.get("enhancement_bearer_melee_damage_bonus"), 1)

        target_unit = _make_unit("Target", army, keywords=["INFANTRY"])
        target_model = _make_model("Target", target_unit, x=1.0, y=0.0, wounds=5)
        target_unit.models = [target_model]
        target_model.parent_unit = target_unit

        melee_parent = SimpleNamespace(is_melee=lambda: True, is_ranged=lambda: False)
        profile = WargearProfile(
            profile_name="Melee",
            wargear_data={
                "range": "Melee",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=melee_parent,
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
        attack_instance = {
            "_aura_attack_mods": aura_stub,
            "mortal_wound": False,
            "mortal_wound_in_addition": False,
        }
        profile._hit_target_with_tracking(
            target_unit, model, attack_instance, roll_value=4, allow_rerolls=False
        )
        self.assertTrue(attack_instance.get("bonus_precision"))

        damage_result = profile._damage_target_with_tracking(
            target_model, model, attack_instance, allow_rerolls=False
        )
        self.assertEqual(damage_result.get("damage_applied"), 2)
        self.assertEqual(target_model.wounds, 3)


if __name__ == "__main__":
    unittest.main()
