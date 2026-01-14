import unittest
from types import SimpleNamespace
from unittest.mock import patch


class _MockDatasheet:
    def __init__(
        self,
        name,
        *,
        ds_id="",
        abilities=None,
        faction_name="Chaos Daemons",
        faction_keywords=None,
        attached_to=None,
        leadership="7",
    ):
        self.id = ds_id
        self.name = name
        self.faction_data = {"name": faction_name}
        self.keywords = []
        self.faction_keywords = list(faction_keywords or [faction_name.upper()])
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": leadership,
                "OC": "1",
                "base_size": "32mm",
                "inv_sv": "7",
                "inv_sv_descr": "none",
            }
        ]
        self.datasheets_wargear = []
        self.datasheets_options = [{"description": "none"}]
        self.datasheets_abilities = list(abilities or [])
        self.loadout = "This model is equipped with: nothing"
        self.attached_to = list(attached_to or [])


def _make_unit(name, *, ds_id="", abilities=None, attached_to=None, leadership="7"):
    from warhammer40k_ai.classes.unit import Unit

    datasheet = _MockDatasheet(
        name,
        ds_id=ds_id,
        abilities=abilities,
        attached_to=attached_to,
        leadership=leadership,
    )
    return Unit(datasheet)


class TestBearerUnitCommonAbilities(unittest.TestCase):
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

    def test_bearer_unit_charge_bonus_applies(self):
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "Instrument of Chaos",
            "description": "Add 1 to Charge rolls made for the bearer's unit.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Instrument of Chaos")
        unit._refresh_bearer_unit_common_modifiers()

        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(unit, 7), 8)

    def test_bearer_unit_advance_and_charge_bonus_applies(self):
        from warhammer40k_ai.classes.game import Battlefield, BattlefieldSize, Game

        ability = {
            "name": "War Drums",
            "description": "While this model is leading a unit, add 1 to Advance and Charge rolls made for that unit.",
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = ["Bodyguard"]

        bodyguard._refresh_bearer_unit_common_modifiers()

        self.assertEqual(bodyguard._apply_advance_roll_modifiers(4), 5)
        game = Game(Battlefield(BattlefieldSize.STRIKE_FORCE))
        self.assertEqual(game._apply_charge_modifiers(bodyguard, 7), 8)

    def test_bearer_unit_objective_control_bonus_applies(self):
        ability = {
            "name": "Banner of Resolve",
            "description": "Add 1 to the Objective Control characteristic of models in the bearer's unit.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Banner of Resolve")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit.objective_control, 2)

    def test_bearer_unit_fnp_applies(self):
        ability = {
            "name": "Pain Icon",
            "description": "Models in the bearer's unit have the Feel No Pain 5+ ability.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Herald", abilities=[ability])
        unit.models[0].optional_wargear.append("Pain Icon")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertIn((5, None), unit.has_feel_no_pain())

    def test_leading_unit_fnp_applies(self):
        ability = {
            "name": "Grim Guardian",
            "description": "While this model is leading a unit, models in that unit have the Feel No Pain 5+ ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Leader", abilities=[ability])
        unit._refresh_bearer_unit_common_modifiers()

        self.assertIn((5, None), unit.has_feel_no_pain())

    def test_bearer_unit_sustained_hits_applies(self):
        from warhammer40k_ai.classes.wargear import WargearProfile

        ability = {
            "name": "Aspect Relic",
            "description": "Weapons equipped by models in the bearer's unit have Sustained Hits 1.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Aspect", abilities=[ability])
        unit.models[0].optional_wargear.append("Aspect Relic")
        unit._refresh_bearer_unit_common_modifiers()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

    def test_leading_unit_melee_sustained_hits_applies_to_melee_only(self):
        from warhammer40k_ai.classes.wargear import WargearProfile

        ability = {
            "name": "Bloody Example",
            "description": "While this model is leading a unit, melee weapons equipped by models in that unit have the [Sustained Hits 1] ability.",
            "type": "Datasheet",
            "parameter": "",
        }
        unit = _make_unit("Leader", abilities=[ability])
        unit._refresh_bearer_unit_common_modifiers()

        melee_parent = SimpleNamespace(name="Melee Blade", is_melee=lambda: True, is_ranged=lambda: False)
        melee_profile = WargearProfile(
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
        ranged_parent = SimpleNamespace(name="Rifle", is_melee=lambda: False, is_ranged=lambda: True)
        ranged_profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=ranged_parent,
        )

        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )

        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            melee_profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 1)

        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=6):
            ranged_profile._hit_target_with_tracking(target, unit.models[0], attack_instance)
        self.assertEqual(int(attack_instance.get("sustained_hit", 0)), 0)

    def test_bearer_unit_ignores_cover_applies(self):
        from warhammer40k_ai.classes.wargear import WargearProfile

        ability = {
            "name": "Shadow Weave",
            "description": "Attacks made by models in the bearer's unit have the Ignores Cover ability.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Shadow", abilities=[ability])
        unit.models[0].optional_wargear.append("Shadow Weave")
        unit._refresh_bearer_unit_common_modifiers()

        parent = SimpleNamespace(name="Test Gun", is_melee=lambda: False, is_ranged=lambda: True)
        profile = WargearProfile(
            profile_name="Ranged",
            wargear_data={
                "range": "24",
                "A": "1",
                "BS_WS": "3+",
                "S": "4",
                "AP": "0",
                "D": "1",
                "description": "",
            },
            parent_wargear=parent,
        )
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda _k: False,
        )
        attack_instance = {"_aura_attack_mods": self._aura_stub()}
        with patch("warhammer40k_ai.classes.wargear.get_roll", return_value=4):
            profile._hit_target_with_tracking(target, unit.models[0], attack_instance)

        self.assertTrue(attack_instance.get("ignores_cover", False))

    def test_bearer_unit_target_hit_penalty_applies(self):
        ability = {
            "name": "Deflective Field",
            "description": "Each time an attack targets the bearer's unit, subtract 1 from the Hit roll.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Shield", abilities=[ability])
        unit.models[0].optional_wargear.append("Deflective Field")
        unit._refresh_bearer_unit_common_modifiers()

        penalty, reasons = unit.get_target_hit_roll_penalty("ranged")
        self.assertEqual(penalty, 1)
        self.assertIn("-1 to hit from Deflective Field", reasons)

    def test_bearer_unit_leadership_set_applies(self):
        ability = {
            "name": "Daemonic Icon",
            "description": "Models in the bearer's unit have a Leadership characteristic of 6+.",
            "type": "Wargear",
            "parameter": "",
        }
        unit = _make_unit("Daemon", abilities=[ability], leadership="7")
        unit.models[0].optional_wargear.append("Daemonic Icon")
        unit._refresh_bearer_unit_common_modifiers()

        self.assertEqual(unit.leadership, 6)

    def test_attached_leader_bearer_unit_leadership_applies_to_bodyguard(self):
        from warhammer40k_ai.classes.army import Army

        ability = {
            "name": "Daemonic Icon",
            "description": "Models in the bearer's unit have a Leadership characteristic of 6+.",
            "type": "Wargear",
            "parameter": "",
        }
        bodyguard = _make_unit("Bodyguard", ds_id="BG1", abilities=[], leadership="5")
        leader = _make_unit("Leader", ds_id="LD1", abilities=[ability], attached_to=["BG1"], leadership="7")
        leader.models[0].optional_wargear.append("Daemonic Icon")

        army = Army("Chaos Daemons", "Detachment")
        army.faction_id = "CD"
        army.add_unit(bodyguard)
        army.add_unit(leader)

        leader.attach_to_unit(bodyguard)

        self.assertEqual(bodyguard.leadership, 6)


if __name__ == "__main__":
    unittest.main()
