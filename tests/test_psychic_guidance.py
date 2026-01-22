import unittest
from types import SimpleNamespace
from unittest.mock import patch

from warhammer40k_ai.units.ability import Ability
from warhammer40k_ai.units.model import Model
from warhammer40k_ai.units.unit import Unit
from warhammer40k_ai.units.wargear import Wargear
from warhammer40k_ai.utility.model_base import Base, BaseType


MODEL_RULE_TEXT = (
    'While this model is within 12" of one or more friendly Aeldari Psyker models, '
    "improve the Ballistic Skill and Weapon Skill characteristics of weapons equipped by this model by 1 "
    "and it has a Leadership characteristic of 6+."
)
UNIT_RULE_TEXT = (
    'While this unit is within 12" of one or more friendly Aeldari Psyker models, '
    "models in this unit have a Leadership characteristic of 6+ and each time a model in this unit makes "
    "an attack, add 1 to the Hit roll."
)


def _make_army(faction_id="AE"):
    return SimpleNamespace(faction_id=faction_id, units=[])


def _make_unit(name, army, *, keywords=None, abilities=None):
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
    unit.faction_keywords = []
    unit.status_effects = []
    unit.special_rules = {}
    unit.possible_abilities = list(abilities or [])
    unit.round_state = SimpleNamespace(remained_stationary_this_round=False, charged_this_round=False)
    unit.attached_leaders = []
    unit.attached_to = None
    unit.embarked_in = None
    unit._ability_cache = {}
    unit._characteristic_modifiers = {}
    unit.starting_model_count = 0
    return unit


def _make_model(name, unit, x, y, *, leadership=7):
    model = Model(
        name=name,
        movement=6,
        toughness=4,
        save=3,
        wounds=2,
        leadership=leadership,
        objective_control=1,
        model_base=Base(BaseType.CIRCULAR, 1.0),
    )
    model.parent_unit = unit
    model.set_location(x, y, 0.0, 0.0)
    return model


def _make_profile(*, melee=False, skill="4+"):
    data = {
        "range": "Melee" if melee else "24",
        "A": "1",
        "BS_WS": skill,
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    parent = Wargear({"name": "Test Weapon", "type": "Melee" if melee else "Ranged", **data})
    return parent.profiles["default"]


class TestPsychicGuidance(unittest.TestCase):
    def test_model_variant_in_range_improves_skill_and_leadership(self):
        army = _make_army()
        ability = Ability("Psychic Guidance", "", MODEL_RULE_TEXT, "Datasheet", "")
        attacker_unit = _make_unit("Wraithlord", army, abilities=[ability])
        attacker_model = _make_model("Wraithlord", attacker_unit, 0.0, 0.0, leadership=7)
        attacker_unit.models = [attacker_model]
        attacker_unit.starting_model_count = 1

        psyker_unit = _make_unit("Farseer", army, keywords=["AELDARI", "PSYKER"])
        psyker_model = _make_model("Farseer", psyker_unit, 10.0, 0.0)
        psyker_unit.models = [psyker_model]
        psyker_unit.starting_model_count = 1

        target_army = _make_army("OP")
        target_unit = _make_unit("Target", target_army)
        target_model = _make_model("Target Model", target_unit, 24.0, 0.0)
        target_unit.models = [target_model]
        target_unit.starting_model_count = 1

        army.units = [attacker_unit, psyker_unit]
        target_army.units = [target_unit]

        profile = _make_profile(skill="4+")
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            hit_result = profile._hit_target_with_tracking(target_unit, attacker_model, {})

        self.assertEqual(hit_result["base_skill"], 3)
        self.assertIn("Psychic Guidance: +1 BS/WS", hit_result["special_effects"])
        self.assertEqual(attacker_unit.get_effective_model_characteristic(attacker_model, "leadership"), 6)

    def test_model_variant_out_of_range_does_not_apply(self):
        army = _make_army()
        ability = Ability("Psychic Guidance", "", MODEL_RULE_TEXT, "Datasheet", "")
        attacker_unit = _make_unit("Wraithlord", army, abilities=[ability])
        attacker_model = _make_model("Wraithlord", attacker_unit, 0.0, 0.0, leadership=7)
        attacker_unit.models = [attacker_model]
        attacker_unit.starting_model_count = 1

        psyker_unit = _make_unit("Farseer", army, keywords=["AELDARI", "PSYKER"])
        psyker_model = _make_model("Farseer", psyker_unit, 15.0, 0.0)
        psyker_unit.models = [psyker_model]
        psyker_unit.starting_model_count = 1

        target_army = _make_army("OP")
        target_unit = _make_unit("Target", target_army)
        target_model = _make_model("Target Model", target_unit, 24.0, 0.0)
        target_unit.models = [target_model]
        target_unit.starting_model_count = 1

        army.units = [attacker_unit, psyker_unit]
        target_army.units = [target_unit]

        profile = _make_profile(skill="4+")
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=3):
            hit_result = profile._hit_target_with_tracking(target_unit, attacker_model, {})

        self.assertEqual(hit_result["base_skill"], 4)
        self.assertNotIn("Psychic Guidance: +1 BS/WS", hit_result["special_effects"])
        self.assertEqual(attacker_unit.get_effective_model_characteristic(attacker_model, "leadership"), 7)

    def test_unit_variant_in_range_adds_hit_bonus_and_leadership(self):
        army = _make_army()
        ability = Ability("Psychic Guidance", "", UNIT_RULE_TEXT, "Datasheet", "")
        attacker_unit = _make_unit("Wraithguard", army, abilities=[ability])
        attacker_model = _make_model("Wraithguard", attacker_unit, 0.0, 0.0, leadership=7)
        attacker_unit.models = [attacker_model]
        attacker_unit.starting_model_count = 1

        psyker_unit = _make_unit("Farseer", army, keywords=["AELDARI", "PSYKER"])
        psyker_model = _make_model("Farseer", psyker_unit, 10.0, 0.0)
        psyker_unit.models = [psyker_model]
        psyker_unit.starting_model_count = 1

        target_army = _make_army("OP")
        target_unit = _make_unit("Target", target_army)
        target_model = _make_model("Target Model", target_unit, 24.0, 0.0)
        target_unit.models = [target_model]
        target_unit.starting_model_count = 1

        army.units = [attacker_unit, psyker_unit]
        target_army.units = [target_unit]

        profile = _make_profile(skill="3+")
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            hit_result = profile._hit_target_with_tracking(target_unit, attacker_model, {})

        self.assertTrue(hit_result["hit"])
        self.assertIn("+1 to hit from Psychic Guidance", hit_result["modifiers"])
        self.assertEqual(attacker_unit.get_effective_model_characteristic(attacker_model, "leadership"), 6)

    def test_unit_variant_out_of_range_does_not_apply(self):
        army = _make_army()
        ability = Ability("Psychic Guidance", "", UNIT_RULE_TEXT, "Datasheet", "")
        attacker_unit = _make_unit("Wraithguard", army, abilities=[ability])
        attacker_model = _make_model("Wraithguard", attacker_unit, 0.0, 0.0, leadership=7)
        attacker_unit.models = [attacker_model]
        attacker_unit.starting_model_count = 1

        psyker_unit = _make_unit("Farseer", army, keywords=["AELDARI", "PSYKER"])
        psyker_model = _make_model("Farseer", psyker_unit, 15.0, 0.0)
        psyker_unit.models = [psyker_model]
        psyker_unit.starting_model_count = 1

        target_army = _make_army("OP")
        target_unit = _make_unit("Target", target_army)
        target_model = _make_model("Target Model", target_unit, 24.0, 0.0)
        target_unit.models = [target_model]
        target_unit.starting_model_count = 1

        army.units = [attacker_unit, psyker_unit]
        target_army.units = [target_unit]

        profile = _make_profile(skill="3+")
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=2):
            hit_result = profile._hit_target_with_tracking(target_unit, attacker_model, {})

        self.assertFalse(hit_result["hit"])
        self.assertNotIn("+1 to hit from Psychic Guidance", hit_result["modifiers"])
        self.assertEqual(attacker_unit.get_effective_model_characteristic(attacker_model, "leadership"), 7)


if __name__ == "__main__":
    unittest.main()
