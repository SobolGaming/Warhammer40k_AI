import unittest
from unittest.mock import patch
from types import SimpleNamespace


class _MockDatasheet:
    def __init__(self, name, *, abilities=None):
        self.name = name
        self.faction_data = {"name": "Test Faction"}
        self.keywords = []
        self.faction_keywords = []
        self.datasheets_unit_composition = [{"description": "1 Test Model"}]
        self.datasheets_models_cost = [{"description": "1 model", "cost": 100}]
        self.datasheets_models = [
            {
                "M": "6",
                "T": "4",
                "Sv": "3",
                "W": "2",
                "Ld": "7",
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
        self.transport = ""


def _make_unit(name, *, abilities=None):
    from warhammer40k_ai.units.unit import Unit

    datasheet = _MockDatasheet(name, abilities=abilities)
    return Unit(datasheet)


def _make_profile(*, weapon_type: str, range_val: str):
    from warhammer40k_ai.units.wargear import Wargear

    data = {
        "range": range_val,
        "A": "1",
        "BS_WS": "3",
        "S": "4",
        "AP": "0",
        "D": "1",
        "description": "",
    }
    parent = Wargear({"name": "Test Weapon", "type": weapon_type, **data})
    return parent.profiles["default"]


class TestLeadingLethalHits(unittest.TestCase):
    def _attach_leader(self, leader, bodyguard):
        bodyguard.attached_leaders = [leader]
        leader.attached_to = bodyguard
        leader.can_be_attached_to = [bodyguard.name]

    def test_leading_lethal_hits_melee(self):
        ability = {
            "name": "Surgical Precision",
            "description": (
                "While this model is leading a unit, weapons equipped by models in that unit have the "
                "[LETHAL HITS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        self._attach_leader(leader, bodyguard)

        profile = _make_profile(weapon_type="Melee", range_val="Melee")
        attacker = SimpleNamespace(name="Attacker", parent_unit=bodyguard)
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("lethal_hit", False))

    def test_leading_lethal_hits_ranged(self):
        ability = {
            "name": "Tactical Precision",
            "description": (
                "While this model is leading a unit, weapons equipped by models in that unit have the "
                "[LETHAL HITS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        self._attach_leader(leader, bodyguard)

        profile = _make_profile(weapon_type="Ranged", range_val="24")
        attacker = SimpleNamespace(name="Attacker", parent_unit=bodyguard)
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )
        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("lethal_hit", False))

    def test_leading_lethal_hits_melee_only(self):
        ability = {
            "name": "Blades of Precision",
            "description": (
                "While this model is leading a unit, melee weapons equipped by models in that unit have the "
                "[LETHAL HITS] ability."
            ),
            "type": "Datasheet",
            "parameter": "",
        }
        leader = _make_unit("Leader", abilities=[ability])
        bodyguard = _make_unit("Bodyguard")
        self._attach_leader(leader, bodyguard)

        melee_profile = _make_profile(weapon_type="Melee", range_val="Melee")
        ranged_profile = _make_profile(weapon_type="Ranged", range_val="24")
        attacker = SimpleNamespace(name="Attacker", parent_unit=bodyguard)
        target = SimpleNamespace(
            toughness=4,
            models=[SimpleNamespace(is_alive=True)],
            has_keyword=lambda k: False,
        )

        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = melee_profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertTrue(attack_instance.get("lethal_hit", False))

        attack_instance = {}
        with patch("warhammer40k_ai.units.wargear.get_roll", return_value=6):
            res = ranged_profile._hit_target_with_tracking(target, attacker, attack_instance)
        self.assertTrue(res["hit"])
        self.assertFalse(attack_instance.get("lethal_hit", False))


if __name__ == "__main__":
    unittest.main()
